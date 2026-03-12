from app.converters import adt_converter, oru_converter, orm_converter, siu_converter, mdm_converter

def dispatch_conversion(msg_type: str, trigger_event: str, hl7_msg):
    """
    Routes the parsed HL7 message to the correct FHIR converter based on message type.
    """
    # Initialize a FHIR Bundle
    bundle = {
        "resourceType": "Bundle",
        "type": "message",
        "entry": []
    }

    # 1. Create MessageHeader from MSH
    import uuid
    from fhir.resources.messageheader import MessageHeader
    
    msh = hl7_msg.msh
    header_data = {
        "id": str(uuid.uuid4()),
        "eventCoding": {
            "system": "http://terminology.hl7.org/CodeSystem/v2-0003",
            "code": f"{msg_type}^{trigger_event}" if trigger_event else msg_type
        },
        "source": {
            "name": msh.msh_3.value if hasattr(msh, 'msh_3') else "Unknown",
            "endpointUrl": "http://example.org/sender/endpoint"
        }
    }

    # Add Sending Facility as a tag or extension if needed, but for now let's put it in source.name or software
    sending_app = msh.msh_3.value if hasattr(msh, 'msh_3') else ""
    sending_fac = msh.msh_4.value if hasattr(msh, 'msh_4') else ""
    if sending_fac:
        header_data["source"]["name"] = f"{sending_app} ({sending_fac})" if sending_app else sending_fac

    # Destination
    dest_app = msh.msh_5.value if hasattr(msh, 'msh_5') else ""
    dest_fac = msh.msh_6.value if hasattr(msh, 'msh_6') else ""
    if dest_app or dest_fac:
        header_data["destination"] = [{
            "name": f"{dest_app} ({dest_fac})" if dest_fac else dest_app,
            "endpointUrl": "http://example.org/reicever/endpoint"
        }]

    from fhir.resources.messageheader import MessageHeader
    header = MessageHeader.parse_obj(header_data)
    bundle["entry"].append({"resource": header.dict(exclude_none=True)})
    
    # Process clinical resources
    resources = []
    
    if msg_type == "ADT":
        resources = adt_converter.convert(hl7_msg)
    elif msg_type == "ORU":
        resources = oru_converter.convert(hl7_msg)
    elif msg_type == "ORM":
        resources = orm_converter.convert(hl7_msg)
    elif msg_type == "SIU":
        resources = siu_converter.convert(hl7_msg)
    elif msg_type == "MDM":
        resources = mdm_converter.convert(hl7_msg)
    else:
        # Unsupported type
        pass

    # Add resources to bundle
    for res in resources:
        bundle["entry"].append({
            "resource": res.dict(exclude_none=True) if hasattr(res, "dict") else res
        })
        
    return bundle
