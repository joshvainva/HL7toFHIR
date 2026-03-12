from hl7apy.parser import parse_message
from hl7apy.exceptions import ParserError, ValidationError

from app.fhir_builder.resource_builder import dispatch_conversion

def parse_hl7_messages(messages_list):
    """
    Takes a list of raw HL7 string messages, parses them using hl7apy,
    and returns a list of dictionaries containing the FHIR result or error.
    """
    results = []
    for idx, raw_msg in enumerate(messages_list):
        if not raw_msg.strip():
            continue
            
        try:
            # Support literal <cr> or <CR> strings (common in copy-pasted HL7 docs)
            clean_msg = raw_msg.strip().replace('<cr>', '\r').replace('<CR>', '\r')
            
            if '\r' not in clean_msg and '\n' in clean_msg:
                # If message only has \n, convert to \r
                clean_msg = clean_msg.replace('\n', '\r')
            elif '\r\n' in clean_msg:
                # If CRLF, convert to \r
                clean_msg = clean_msg.replace('\r\n', '\r')
                
            # Parse with validation disabled to allow partial or slightly non-conformant messages
            hl7_msg = parse_message(clean_msg, force_validation=False)
            
            # Extract message type from MSH.9
            msh = hl7_msg.msh
            msg_type = ""
            trigger_event = ""
            
            try:
                msg_type = msh.msh_9.msh_9_1.value
                if hasattr(msh.msh_9, 'msh_9_2'):
                    trigger_event = msh.msh_9.msh_9_2.value
            except AttributeError:
                # Default if something is missing
                msg_type = "UNKNOWN"
            
            message_identifier = f"{msg_type}^{trigger_event}" if trigger_event else msg_type
            
            # Dispatch to appropriate FHIR converter
            fhir_bundle = dispatch_conversion(msg_type, trigger_event, hl7_msg)
            
            # Check for application errors in MSA segment (especially for ACKs)
            status = "success"
            error_msg = None
            
            try:
                msa_segs = [c for c in hl7_msg.children if c.name == 'MSA']
                if msa_segs:
                    msa = msa_segs[0]
                    # AA = Accept, AE = Error, AR = Reject
                    msa_status = msa.msa_1.value if hasattr(msa, 'msa_1') else ""
                    if msa_status in ['AE', 'AR']:
                        status = "error"
                        error_msg = msa.msa_3.value if hasattr(msa, 'msa_3') else f"HL7 Application Error ({msa_status})"
            except:
                pass

            response = {
                "index": idx + 1,
                "status": status,
                "message_type": message_identifier,
                "fhir": fhir_bundle,
                "raw_snippet": raw_msg[:50] + "..."
            }
            if error_msg:
                response["error_message"] = error_msg
            
            results.append(response)
            
        except Exception as e:
            results.append({
                "index": idx + 1,
                "status": "error",
                "error_message": str(e),
                "raw_snippet": raw_msg[:50] + "..." if isinstance(raw_msg, str) else "Unknown format"
            })
            
    return results
