import uuid
from fhir.resources.patient import Patient
from fhir.resources.appointment import Appointment
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
        
        # Telecom (PID-13)
        if hasattr(pid, 'pid_13'):
            telecoms = []
            field_list = pid.pid_13 if isinstance(pid.pid_13, list) else [pid.pid_13]
            for xtn in field_list:
                if hasattr(xtn, 'xtn_1') and xtn.xtn_1.value:
                    telecoms.append({"system": "phone", "value": xtn.xtn_1.value, "use": "home"})
            if telecoms:
                patient_data["telecom"] = telecoms

    patient_res = Patient.parse_obj(patient_data)
    resources.append(patient_res)

    # -------------------------------------------------------
    # SCH -> Appointment
    # -------------------------------------------------------
    sch_segs = find_segments(hl7_msg, 'SCH')
    if sch_segs:
        sch = sch_segs[0]
        
        # Appointment Status (SCH-25)
        status_map = {
            "Scheduled": "booked",
            "Confirmed": "booked",
            "Canceled": "cancelled",
            "Complete": "fulfilled",
            "No Show": "noshow"
        }
        hl7_status = sch.sch_25.value if hasattr(sch, 'sch_25') else "Scheduled"
        fhir_status = status_map.get(hl7_status, "booked")

        # Description (SCH-7)
        description = sch.sch_7.value if hasattr(sch, 'sch_7') else "Reason for appointment"

        # Timing (SCH-11)
        # SCH-11.4 Start Time, SCH-11.5 End Time
        start_time = None
        end_time = None
        if hasattr(sch, 'sch_11'):
            if hasattr(sch.sch_11, 'sch_11_4') and sch.sch_11.sch_11_4.value:
                st = sch.sch_11.sch_11_4.value
                if len(st) >= 12:
                    start_time = f"{st[0:4]}-{st[4:6]}-{st[6:8]}T{st[8:10]}:{st[10:12]}:00Z"
            if hasattr(sch.sch_11, 'sch_11_5') and sch.sch_11.sch_11_5.value:
                et = sch.sch_11.sch_11_5.value
                if len(et) >= 12:
                    end_time = f"{et[0:4]}-{et[4:6]}-{et[6:8]}T{et[8:10]}:{et[10:12]}:00Z"

        # Participants (Patient + AIP/AIL/AIG)
        participants = [
            {
                "actor": {"reference": f"Patient/{patient_id}"},
                "status": "accepted"
            }
        ]

        # AIP Personnel
        aip_segs = find_segments(hl7_msg, 'AIP')
        for aip in aip_segs:
            if hasattr(aip, 'aip_3') and aip.aip_3.value:
                 p_name = aip.aip_3.value
                 participants.append({
                     "actor": {"display": p_name},
                     "status": "accepted"
                 })

        appt_data = {
            "id": str(uuid.uuid4()),
            "status": fhir_status,
            "description": description,
            "participant": participants
        }
        if start_time: appt_data["start"] = start_time
        if end_time: appt_data["end"] = end_time

        appt = Appointment.parse_obj(appt_data)
        resources.append(appt)

    return resources
