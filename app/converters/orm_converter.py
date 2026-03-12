import uuid
from fhir.resources.patient import Patient
from fhir.resources.servicerequest import ServiceRequest
from fhir.resources.humanname import HumanName
from fhir.resources.condition import Condition
from fhir.resources.codeableconcept import CodeableConcept

def convert(hl7_msg):
    resources = []
    patient_id = None
    
    # Helper to build Patient Name
    def build_name(pid):
        if not hasattr(pid, 'pid_5'):
            return None
        name = HumanName()
        has_name = False
        if hasattr(pid.pid_5, 'pid_5_1') and pid.pid_5.pid_5_1.value:
            name.family = pid.pid_5.pid_5_1.value
            has_name = True
        if hasattr(pid.pid_5, 'pid_5_2') and pid.pid_5.pid_5_2.value:
            name.given = [pid.pid_5.pid_5_2.value]
            has_name = True
        return name if has_name else None

    # Extract PID -> Patient from ORM_O01_PATIENT group
    patient_group = getattr(hl7_msg, 'orm_o01_patient', None)
    if patient_group and hasattr(patient_group, 'pid'):
        patient = Patient.construct(id=str(uuid.uuid4()))
        patient_id = patient.id
        
        name = build_name(patient_group.pid)
        if name:
            patient.name = [name]
            
        resources.append(patient)
    # Extract PID directly if it's top level
    elif hasattr(hl7_msg, 'pid'):
        patient = Patient.construct(id=str(uuid.uuid4()))
        patient_id = patient.id
        
        name = build_name(hl7_msg.pid)
        if name:
            patient.name = [name]
            
        resources.append(patient)
        
    def find_segments(group, tgt_name):
        segments = []
        try:
            for child in group.children:
                if child.name == tgt_name:
                    segments.append(child)
                else:
                    # Recursively search all subgroups
                    segments.extend(find_segments(child, tgt_name))
        except AttributeError:
            # Not a group with children
            pass
        return segments

    # ORC or OBR -> ServiceRequest
    obr_segments = find_segments(hl7_msg, 'OBR')
    for segment in obr_segments:
        sr_data = {
            "id": str(uuid.uuid4()),
            "status": "active",
            "intent": "order",
            "subject": {"reference": f"Patient/{patient_id}" if patient_id else "Patient/unknown"}
        }
        if hasattr(segment, 'obr_4') and segment.obr_4.value:
            sr_data["code"] = {"text": segment.obr_4.value}
        # OBR-4 is a CE field - try to get code and display name
        if hasattr(segment, 'obr_4') and hasattr(segment.obr_4, 'obr_4_1') and segment.obr_4.obr_4_1.value:
            code_id = segment.obr_4.obr_4_1.value
            display = segment.obr_4.obr_4_2.value if hasattr(segment.obr_4, 'obr_4_2') else code_id
            sr_data["code"] = {"coding": [{"code": code_id, "display": display}], "text": display}
        sr = ServiceRequest.construct(**sr_data)
        resources.append(sr)
        
    # DG1 -> Condition
    dg1_segments = find_segments(hl7_msg, 'DG1')
    for segment in dg1_segments:
        # Extract DG1-3 (diagnosis code)
        diag_code = None
        diag_display = None
        if hasattr(segment, 'dg1_3'):
            if hasattr(segment.dg1_3, 'dg1_3_1') and segment.dg1_3.dg1_3_1.value:
                diag_code = segment.dg1_3.dg1_3_1.value
            if hasattr(segment.dg1_3, 'dg1_3_2') and segment.dg1_3.dg1_3_2.value:
                diag_display = segment.dg1_3.dg1_3_2.value

        condition_data = {
            "id": str(uuid.uuid4()),
            "subject": {"reference": f"Patient/{patient_id}" if patient_id else "Patient/unknown"}
        }
        if diag_code or diag_display:
            coding = []
            if diag_code:
                coding.append({"code": diag_code, "display": diag_display or diag_code})
            condition_data["code"] = {
                "coding": coding,
                "text": diag_display or diag_code
            }

        condition = Condition.construct(**condition_data)
        resources.append(condition)

    return resources
