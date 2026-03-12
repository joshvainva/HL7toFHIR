# HL7 to FHIR Converter

A modern, fast, and elegant web application to convert legacy HL7 v2 messages into FHIR JSON resources.

## Features

- **Modern Web Interface**: Premium UI with glassmorphism, responsive design, and smooth interactions.
- **Multiple Inputs**: Paste HL7 messages manually or drag-and-drop multiple `.hl7` or `.txt` files.
- **Robust Parsing**: Uses `hl7apy` to accurately parse HL7 segments.
- **Dedicated Converters**: Supports modular, extensible mapping to `fhir.resources` models.
- **Extensible Architecture**: Easy to slot in new message types or update FHIR structural mappings.

### Supported Integrations
- **ADT (Admit, Discharge, Transfer)** -> Maps to `Patient` and `Encounter`
- **ORU (Observation Result)** -> Maps to `Patient`, `DiagnosticReport`, and `Observation`
- **ORM (Order Entry)** -> Maps to `Patient` and `ServiceRequest`
- **SIU (Scheduling Information)** -> Maps to `Patient` and `Appointment`
- **MDM (Medical Document Management)** -> Maps to `Patient`, `DocumentReference`, and `Attachment`

## Setup Instructions

### Prerequisites
- Docker (recommended) OR
- Python 3.11+ and `pip`

### Method 1: Using Docker (Recommended)

1. **Build the image**:
   ```bash
   docker build -t hl7-fhir-converter .
   ```
2. **Run the container**:
   ```bash
   docker run -p 8000:8000 hl7-fhir-converter
   ```
3. Open your browser to [http://localhost:8000](http://localhost:8000)

### Method 2: Running Locally

1. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Start the server**:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Open your browser to [http://localhost:8000](http://localhost:8000)

## API Documentation

FastAPI auto-generates Swagger documentation. After starting the server, you can view the docs at:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Endpoint: `POST /convert`
Accepts `multipart/form-data`:
- `hl7_text` (optional string): Raw HL7 message(s).
- `files` (optional list of files): Uploaded `.hl7` or `.txt` files.

Returns a JSON object containing the conversion results (a list with status and generated FHIR resources).

## Testing

Example HL7 messages are provided in the `samples/` directory. You can drag and drop these into the web interface to see how the conversion works.
