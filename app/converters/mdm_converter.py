import uuid
from fhir.resources.patient import Patient
from fhir.resources.documentreference import DocumentReference
from fhir.resources.humanname import HumanName

def convert(hl7_msg):
    resources = []
    patient_id = str(uuid.uuid4())

    # -------------------------------------------------------
    # Helper: recursive segment finder
    # -------------------------------------------------------
    def find_segments(group, tgt_name):
        found = []
        try:
            for child in group.children:
                if child.name == tgt_name:
                    found.append(child)
                else:
                    found.extend(find_segments(child, tgt_name))
        except AttributeError:
            pass
        return found

    # -------------------------------------------------------
    # PID -> Patient
    # -------------------------------------------------------
    pid_segs = find_segments(hl7_msg, 'PID')
    pid = pid_segs[0] if pid_segs else None

    patient_data = {"id": patient_id}

    if pid:
        # Name (PID-5)
        if hasattr(pid, 'pid_5'):
            family = None
            given = None
            if hasattr(pid.pid_5, 'pid_5_1') and pid.pid_5.pid_5_1.value:
                family = pid.pid_5.pid_5_1.value
            if hasattr(pid.pid_5, 'pid_5_2') and pid.pid_5.pid_5_2.value:
                given = pid.pid_5.pid_5_2.value
            if family or given:
                name_data = {}
                if family: name_data["family"] = family
                if given: name_data["given"] = [given]
                patient_data["name"] = [name_data]

        # Gender (PID-8)
        if hasattr(pid, 'pid_8') and pid.pid_8.value:
            gender_map = {'M': 'male', 'F': 'female', 'O': 'other', 'U': 'unknown'}
            patient_data["gender"] = gender_map.get(pid.pid_8.value, 'unknown')

        # Birth Date (PID-7)
        if hasattr(pid, 'pid_7') and pid.pid_7.value:
            dob = pid.pid_7.value
            if len(dob) >= 8:
                patient_data["birthDate"] = f"{dob[0:4]}-{dob[4:6]}-{dob[6:8]}"

    patient_res = Patient.construct(**patient_data)
    resources.append(patient_res)

    # -------------------------------------------------------
    # TXA -> DocumentReference
    # -------------------------------------------------------
    txa_segs = find_segments(hl7_msg, 'TXA')
    obx_segs = find_segments(hl7_msg, 'OBX')

    if txa_segs or obx_segs:
        doc_data = {
            "id": str(uuid.uuid4()),
            "status": "current",
            "subject": {"reference": f"Patient/{patient_id}"}
        }

        # TXA Mapping
        if txa_segs:
            txa = txa_segs[0]
            # TXA-2: Document Type
            if hasattr(txa, 'txa_2') and txa.txa_2.value:
                doc_data["type"] = {"text": txa.txa_2.value}
            
            # TXA-12: Document Description or ID
            if hasattr(txa, 'txa_12') and txa.txa_12.value:
                doc_data["description"] = txa.txa_12.value

        # OBX mapping to content.attachment
        contents = []
        for obx in obx_segs:
            if hasattr(obx, 'obx_5') and obx.obx_5.value:
                text_content = obx.obx_5.value
                # In a real app we might base64 encode this or use data directly if short
                # FHIR Attachment.data is base64Binary. For display we can use a string if bypassing validation
                # but better to stick to the structure. 
                attachment_data = {
                    "contentType": "text/plain",
                    "data": text_content, # Construct bypasses validation, so we can put text here for simplicity in this demo
                    "title": "Document Content"
                }
                contents.append({"attachment": attachment_data})
        
        if contents:
            doc_data["content"] = contents
        else:
            # DocumentReference MUST have content in FHIR if we want it to be valid
            doc_data["content"] = [{"attachment": {"title": "Empty Document"}}]

        doc_res = DocumentReference.construct(**doc_data)
        resources.append(doc_res)

    return resources
