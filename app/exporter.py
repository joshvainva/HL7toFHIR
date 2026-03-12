from fpdf import FPDF
import json

def json_to_xml(bundle_json):
    """
    Convert FHIR Bundle JSON to XML using fhir.resources.
    """
    try:
        from fhir.resources.bundle import Bundle
        # use parse_obj to recursively build models from the dict
        bundle = Bundle.parse_obj(bundle_json)
        # With lxml installed, pretty_print=True is the correct parameter
        return bundle.xml(pretty_print=True)
    except Exception as e:
        return f"<!-- Error converting to XML: {str(e)} -->"

class FHIRPDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 15)
        self.cell(0, 10, 'FHIR Conversion Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf(bundle_json):
    """
    Generate a human-readable PDF from a FHIR Bundle.
    """
    pdf = FHIRPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=10)

    results = bundle_json.get("results", [])
    if not results:
        pdf.cell(0, 10, "No data found.", ln=True)
        return bytes(pdf.output())

    for res_wrapper in results:
        idx = res_wrapper.get("index", "?")
        msg_type = res_wrapper.get("message_type", "Unknown")
        status = res_wrapper.get("status", "success")
        
        pdf.set_fill_color(240, 240, 240)
        pdf.set_font("helvetica", 'B', 12)
        pdf.cell(0, 10, f"Message {idx}: {msg_type} ({status})", ln=True, fill=True)
        pdf.ln(2)

        bundle = res_wrapper.get("fhir", {})
        entries = bundle.get("entry", [])
        
        if not entries:
            pdf.set_font("helvetica", 'I', 10)
            pdf.cell(0, 8, "No resources generated for this message.", ln=True)
        
        for entry in entries:
            resource = entry.get("resource", {})
            rt = resource.get("resourceType", "Unknown")
            
            pdf.set_font("helvetica", 'B', 11)
            pdf.cell(0, 8, f"Resource: {rt}", ln=True)
            pdf.set_font("helvetica", size=10)
            
            # Detailed attribute extraction
            if rt == "MessageHeader":
                event = resource.get("eventCoding", {}).get("code", "N/A")
                source = resource.get("source", {}).get("name", "N/A")
                dests = resource.get("destination", [])
                dest = dests[0].get("name", "N/A") if dests else "N/A"
                pdf.multi_cell(0, 6, f"  Event: {event}\n  Source: {source}\n  Destination: {dest}")

            elif rt == "Patient":
                name = resource.get("name", [{}])[0]
                family = name.get("family", "")
                given = " ".join(name.get("given", []))
                gender = resource.get("gender", "")
                dob = resource.get("birthDate", "")
                telecom = resource.get("telecom", [{}])[0].get("value", "N/A")
                
                pdf.multi_cell(0, 6, f"  Name: {given} {family}\n  Gender: {gender}\n  DOB: {dob}\n  Phone: {telecom}")
            
            elif rt == "Encounter":
                # In R5 class is a list of CodeableConcept
                classes = resource.get("class", [])
                class_str = "N/A"
                if classes:
                    # Get the display/code from the first coding of the first class
                    first_class = classes[0]
                    codings = first_class.get("coding", [])
                    if codings:
                        class_str = codings[0].get("display", codings[0].get("code", "N/A"))
                    else:
                        class_str = first_class.get("text", "N/A")
                
                status = resource.get("status", "")
                pdf.cell(0, 6, f"  Class: {class_str}", ln=True)
                pdf.cell(0, 6, f"  Status: {status}", ln=True)
            
            elif rt == "Observation":
                code = resource.get("code", {}).get("text", "")
                val = resource.get("valueQuantity", {}).get("value", "")
                unit = resource.get("valueQuantity", {}).get("unit", "")
                pdf.cell(0, 6, f"  Result: {code} = {val} {unit}", ln=True)
            
            elif rt == "Appointment":
                start = resource.get("start", "N/A")
                end = resource.get("end", "N/A")
                desc = resource.get("description", "N/A")
                status = resource.get("status", "N/A")
                pdf.multi_cell(0, 6, f"  Scheduled: {start} to {end}\n  Description: {desc}\n  Status: {status}")
            
            elif rt == "DiagnosticReport":
                code = resource.get("code", [{}])[0].get("text", "")
                pdf.cell(0, 6, f"  Report: {code}", ln=True)

            pdf.ln(2)
        pdf.ln(5)

    return bytes(pdf.output())
