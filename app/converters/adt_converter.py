import uuid

from fhir.resources.patient import Patient
from fhir.resources.encounter import Encounter
from fhir.resources.humanname import HumanName
from fhir.resources.address import Address
from fhir.resources.coverage import Coverage


def convert(hl7_msg):
    resources = []
    patient_id = str(uuid.uuid4())

    # -------------------------------------------------------
    # Helper: recursive segment finder (same pattern as ORM)
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
    # Helper: Title Case
    # -------------------------------------------------------
    def title_case(text):
        if not text: return text
        return text.title()

    # -------------------------------------------------------
    # PID -> Patient  (construct bypasses pydantic validation)
    # -------------------------------------------------------
    pid_segs = find_segments(hl7_msg, 'PID')
    pid = pid_segs[0] if pid_segs else None

    patient_data = {
        "id": patient_id,
        "active": True
    }

    if pid:
        # Name (PID-5)
        if hasattr(pid, 'pid_5'):
            family = None
            given = []
            
            if hasattr(pid.pid_5, 'pid_5_1') and pid.pid_5.pid_5_1.value:
                family = title_case(pid.pid_5.pid_5_1.value)
            if hasattr(pid.pid_5, 'pid_5_2') and pid.pid_5.pid_5_2.value:
                given.append(title_case(pid.pid_5.pid_5_2.value))
            # Middle name (PID-5.3)
            if hasattr(pid.pid_5, 'pid_5_3') and pid.pid_5.pid_5_3.value:
                given.append(title_case(pid.pid_5.pid_5_3.value))
                
            if family or given:
                name_data = {"use": "official"}
                if family:
                    name_data["family"] = family
                if given:
                    name_data["given"] = given
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

        # Address (PID-11)
        if hasattr(pid, 'pid_11'):
            addr_data = {}
            if hasattr(pid.pid_11, 'pid_11_1') and pid.pid_11.pid_11_1.value:
                addr_data["line"] = [title_case(pid.pid_11.pid_11_1.value)]
            if hasattr(pid.pid_11, 'pid_11_3') and pid.pid_11.pid_11_3.value:
                addr_data["city"] = title_case(pid.pid_11.pid_11_3.value)
            if hasattr(pid.pid_11, 'pid_11_4') and pid.pid_11.pid_11_4.value:
                addr_data["state"] = pid.pid_11.pid_11_4.value  # States usually keep uppercase codes
            if hasattr(pid.pid_11, 'pid_11_5') and pid.pid_11.pid_11_5.value:
                addr_data["postalCode"] = pid.pid_11.pid_11_5.value
            if hasattr(pid.pid_11, 'pid_11_6') and pid.pid_11.pid_11_6.value:
                addr_data["country"] = pid.pid_11.pid_11_6.value
            if addr_data:
                patient_data["address"] = [addr_data]

        # Telecom (PID-13: home phone/email, PID-14: work phone)
        telecoms = []

        def extract_telecom(field, use_label):
            """Extract phone and/or email from an XTN field."""
            entries = []
            # PID-13 can be a list of XTN fields
            field_list = field if isinstance(field, list) else [field]
            for xtn in field_list:
                phone = None
                email = None
                if hasattr(xtn, 'xtn_1') and xtn.xtn_1.value:
                    phone = xtn.xtn_1.value
                if hasattr(xtn, 'xtn_4') and xtn.xtn_4.value:
                    email = xtn.xtn_4.value
                if phone:
                    entries.append({"system": "phone", "value": phone, "use": use_label})
                if email:
                    entries.append({"system": "email", "value": email, "use": use_label})
            return entries

        if hasattr(pid, 'pid_13'):
            telecoms.extend(extract_telecom(pid.pid_13, "home"))
        if hasattr(pid, 'pid_14'):
            telecoms.extend(extract_telecom(pid.pid_14, "work"))

        if telecoms:
            patient_data["telecom"] = telecoms

    patient = Patient.construct(**patient_data)
    resources.append(patient)

    # -------------------------------------------------------
    # PV1 -> Encounter
    # -------------------------------------------------------
    pv1_segs = find_segments(hl7_msg, 'PV1')
    if pv1_segs:
        pv1 = pv1_segs[0]

        # PV1-2: Patient class (I=Inpatient, O=Outpatient, E=Emergency, etc.)
        class_code = "AMB"  # default outpatient / ambulatory
        class_display = "ambulatory"
        if hasattr(pv1, 'pv1_2') and pv1.pv1_2.value:
            class_map = {
                'I': ('IMP', 'inpatient encounter'),
                'O': ('AMB', 'ambulatory'),
                'E': ('EMER', 'emergency'),
                'P': ('PRENC', 'pre-admission'),
                'R': ('AMB', 'recurring'),
                'B': ('AMB', 'obstetrics'),
                'N': ('IMP', 'newborn'),
            }
            code, display = class_map.get(pv1.pv1_2.value, ('AMB', 'ambulatory'))
            class_code, class_display = code, display
        encounter_data = {
            "id": str(uuid.uuid4()),
            "status": "unknown",
            "class": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                            "code": class_code,
                            "display": class_display
                        }
                    ]
                }
            ],
            "subject": {"reference": f"Patient/{patient_id}"}
        }

        encounter = Encounter.construct(**encounter_data)
        resources.append(encounter)

    # -------------------------------------------------------
    # IN1 -> Coverage (Insurance)
    # -------------------------------------------------------
    in1_segs = find_segments(hl7_msg, 'IN1')
    for in1 in in1_segs:
        coverage_data = {
            "id": str(uuid.uuid4()),
            "status": "active",
            "beneficiary": {"reference": f"Patient/{patient_id}"}
        }

        # IN1-4: Insurance company name
        if hasattr(in1, 'in1_4') and in1.in1_4.value:
            coverage_data["payor"] = [{"display": in1.in1_4.value}]

        # IN1-3: Insurance plan ID (use as identifier)
        if hasattr(in1, 'in1_3') and in1.in1_3.value:
            coverage_data["identifier"] = [{"value": in1.in1_3.value}]

        coverage = Coverage.construct(**coverage_data)
        resources.append(coverage)

    return resources
