import uuid


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

    from fhir.resources.patient import Patient
    patient = Patient.construct(**patient_data)
    resources.append(patient)

    # -------------------------------------------------------
    # OBR -> DiagnosticReport  (one per OBR group)
    # -------------------------------------------------------
    from fhir.resources.diagnosticreport import DiagnosticReport
    from fhir.resources.observation import Observation

    obr_segs = find_segments(hl7_msg, 'OBR')

    for obr in obr_segs:
        report_id = str(uuid.uuid4())

        # OBR-4: Universal Service Identifier (test ordered)
        report_code = {"coding": [], "text": "Lab Report"}
        if hasattr(obr, 'obr_4'):
            code_id = None
            code_display = None
            if hasattr(obr.obr_4, 'obr_4_1') and obr.obr_4.obr_4_1.value:
                code_id = obr.obr_4.obr_4_1.value
            if hasattr(obr.obr_4, 'obr_4_2') and obr.obr_4.obr_4_2.value:
                code_display = obr.obr_4.obr_4_2.value
            if code_id or code_display:
                report_code = {
                    "coding": [{"code": code_id or code_display, "display": code_display or code_id}],
                    "text": code_display or code_id
                }

        # OBR-7: Observation date/time
        effective_dt = None
        if hasattr(obr, 'obr_7') and obr.obr_7.value:
            dt = obr.obr_7.value
            if len(dt) >= 8:
                effective_dt = f"{dt[0:4]}-{dt[4:6]}-{dt[6:8]}"

        report_data = {
            "id": report_id,
            "status": "final",
            "code": report_code,
            "subject": {"reference": f"Patient/{patient_id}"}
        }
        if effective_dt:
            report_data["effectiveDateTime"] = effective_dt

        report = DiagnosticReport.construct(**report_data)
        resources.append(report)

        # -------------------------------------------------------
        # OBX -> Observation  (find OBX segments under this OBR)
        # Find OBX siblings in same parent group as this OBR
        # -------------------------------------------------------
        # Strategy: collect all OBX in the whole message; they follow OBR in the group
        # We'll group OBX by proximity to its parent OBR group using hl7apy structure.
        # If only one OBR, all OBX belong to it.
        obx_segs = find_segments(hl7_msg, 'OBX')

        obs_references = []
        for obx in obx_segs:
            obs_id = str(uuid.uuid4())

            # OBX-3: Observation identifier (code)
            obs_code = {"coding": [], "text": "Observation"}
            if hasattr(obx, 'obx_3'):
                local_code = None
                local_display = None
                loinc_code = None
                loinc_display = None
                # obx_3 is CWE: component 1=local code, 2=local text, 4=LOINC code, 5=LOINC display
                if hasattr(obx.obx_3, 'obx_3_1') and obx.obx_3.obx_3_1.value:
                    local_code = obx.obx_3.obx_3_1.value
                if hasattr(obx.obx_3, 'obx_3_2') and obx.obx_3.obx_3_2.value:
                    local_display = obx.obx_3.obx_3_2.value
                if hasattr(obx.obx_3, 'obx_3_4') and obx.obx_3.obx_3_4.value:
                    loinc_code = obx.obx_3.obx_3_4.value
                if hasattr(obx.obx_3, 'obx_3_5') and obx.obx_3.obx_3_5.value:
                    loinc_display = obx.obx_3.obx_3_5.value

                codings = []
                if loinc_code:
                    codings.append({
                        "system": "http://loinc.org",
                        "code": loinc_code,
                        "display": loinc_display or local_display or loinc_code
                    })
                if local_code:
                    codings.append({
                        "system": "local",
                        "code": local_code,
                        "display": local_display or local_code
                    })
                obs_code = {
                    "coding": codings,
                    "text": local_display or loinc_display or local_code or "Observation"
                }

            # OBX-2: Value type, OBX-5: Value, OBX-6: Units
            value_type = None
            if hasattr(obx, 'obx_2') and obx.obx_2.value:
                value_type = obx.obx_2.value

            obs_data = {
                "id": obs_id,
                "status": "final",
                "code": obs_code,
                "subject": {"reference": f"Patient/{patient_id}"}
            }

            # Map value based on OBX-2 type
            if hasattr(obx, 'obx_5') and obx.obx_5.value:
                raw_val = obx.obx_5.value
                if value_type == 'NM':
                    # Numeric value with units (OBX-6)
                    unit_text = None
                    unit_code = None
                    if hasattr(obx, 'obx_6') and obx.obx_6.value:
                        unit_text = obx.obx_6.value
                        unit_code = unit_text
                    try:
                        obs_data["valueQuantity"] = {
                            "value": float(raw_val),
                            "unit": unit_text or "",
                            "system": "http://unitsofmeasure.org",
                            "code": unit_code or ""
                        }
                    except ValueError:
                        obs_data["valueString"] = raw_val
                elif value_type == 'SN':
                    # Structured Numeric (e.g. ^182 or >10)
                    # SN_1: Comparator, SN_2: Num1, SN_3: Separator/Suffix, SN_4: Num2
                    unit_text = obx.obx_6.value if hasattr(obx, 'obx_6') and obx.obx_6.value else ""
                    
                    qty_data = {
                        "unit": unit_text,
                        "system": "http://unitsofmeasure.org",
                        "code": unit_text
                    }
                    
                    try:
                        comp = ""
                        val = None
                        
                        # Robust extraction: Prioritize raw splitting if separators are present
                        # because hl7apy often struggles with 'varies' child components
                        if '^' in str(raw_val):
                            parts = str(raw_val).split('^')
                            if len(parts) >= 1: comp = parts[0]
                            if len(parts) >= 2: val = parts[1]
                        else:
                            # Try structural access as fallback
                            try:
                                if hasattr(obx.obx_5, 'sn_1') and obx.obx_5.sn_1.value:
                                    comp = obx.obx_5.sn_1.value
                                if hasattr(obx.obx_5, 'sn_2') and obx.obx_5.sn_2.value:
                                    val = obx.obx_5.sn_2.value
                            except Exception:
                                pass
                        
                        # FHIR comparators: <, <=, >=, >
                        if comp in ['<', '<=', '>=', '>']:
                            qty_data["comparator"] = comp
                        
                        # Handle value conversion
                        if val:
                            try:
                                qty_data["value"] = float(val)
                                obs_data["valueQuantity"] = qty_data
                            except ValueError:
                                obs_data["valueString"] = raw_val
                        else:
                            obs_data["valueString"] = raw_val
                    except Exception:
                        obs_data["valueString"] = raw_val
                else:
                    obs_data["valueString"] = raw_val

            # OBX-7: Reference range
            if hasattr(obx, 'obx_7') and obx.obx_7.value:
                ref_range = obx.obx_7.value
                # Parse "low-high" format
                parts = ref_range.split('-')
                try:
                    ref_range_data = {"text": ref_range}
                    if len(parts) == 2:
                        ref_range_data["low"] = {"value": float(parts[0])}
                        ref_range_data["high"] = {"value": float(parts[1])}
                    obs_data["referenceRange"] = [ref_range_data]
                except ValueError:
                    obs_data["referenceRange"] = [{"text": ref_range}]

            # OBX-8: Abnormal flags
            if hasattr(obx, 'obx_8') and obx.obx_8.value:
                flag = obx.obx_8.value
                flag_map = {'H': 'H', 'L': 'L', 'A': 'A', 'AA': 'AA', 'HH': 'HH', 'LL': 'LL'}
                if flag in flag_map:
                    obs_data["interpretation"] = [{
                        "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "code": flag_map[flag]}],
                        "text": flag
                    }]

            # OBX-14: Date of observation
            if hasattr(obx, 'obx_14') and obx.obx_14.value:
                dt = obx.obx_14.value
                if len(dt) >= 8:
                    obs_data["effectiveDateTime"] = f"{dt[0:4]}-{dt[4:6]}-{dt[6:8]}"

            obs = Observation.construct(**obs_data)
            resources.append(obs)
            obs_references.append({"reference": f"Observation/{obs_id}"})

        # Link observations back to DiagnosticReport
        if obs_references:
            report.result = obs_references

    return resources
