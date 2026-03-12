document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('convert-form');
    const fileUpload = document.getElementById('file_upload');
    const dropArea = document.querySelector('.file-drop-area');
    const fileList = document.getElementById('file_list');
    const convertBtn = document.getElementById('convert-btn');
    const btnText = document.querySelector('.btn-text');
    const btnLoader = document.querySelector('.btn-loader');
    
    const outputEmptyState = document.getElementById('output-empty-state');
    const jsonOutput = document.getElementById('json-output');
    const viewToggle = document.getElementById('view-toggle');
    const toggleBtns = document.querySelectorAll('.toggle-btn');
    
    // Action Buttons
    const copyBtn = document.getElementById('copy-btn');
    const downloadJsonBtn = document.getElementById('download-json-btn');
    const downloadXmlBtn = document.getElementById('download-xml-btn');
    const downloadPdfBtn = document.getElementById('download-pdf-btn');
    
    let currentOutput = null;
    let currentView = 'json';

    // --- File Drag and Drop logic ---
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.add('drag-over'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropArea.addEventListener(eventName, () => dropArea.classList.remove('drag-over'), false);
    });

    dropArea.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileUpload.files = files; // Assign files to input
        updateFileList();
    });

    fileUpload.addEventListener('change', updateFileList);

    function updateFileList() {
        if (fileUpload.files.length > 0) {
            let listHtml = '';
            for (let i = 0; i < fileUpload.files.length; i++) {
                listHtml += `<div>📄 ${fileUpload.files[i].name}</div>`;
            }
            fileList.innerHTML = listHtml;
        } else {
            fileList.innerHTML = '';
        }
    }

    // --- Form Submission ---
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const hl7Text = document.getElementById('hl7_text').value.trim();
        const hasFiles = fileUpload.files.length > 0;
        
        if (!hl7Text && !hasFiles) {
            alert('Please provide an HL7 message either via text or file upload.');
            return;
        }

        if (hl7Text && hasFiles) {
            alert('Please provide EITHER text input OR a file upload, not both.');
            return;
        }

        const formData = new FormData(form);

        // UI Loading State
        btnText.style.display = 'none';
        btnLoader.style.display = 'block';
        convertBtn.disabled = true;
        
        try {
            const response = await fetch('/convert', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Network response was not ok');
            }

            const data = await response.json();
            
            // Format and Display Output
            currentOutput = data;
            outputEmptyState.style.display = 'none';
            jsonOutput.classList.add('active');
            viewToggle.style.display = 'flex';
            
            renderOutput();
            
            // Enable actions
            [copyBtn, downloadJsonBtn, downloadXmlBtn, downloadPdfBtn].forEach(btn => btn.disabled = false);
            
        } catch (error) {
            console.error('Error during conversion:', error);
            alert('An error occurred during conversion. Please check the logs.');
            
            outputEmptyState.style.display = 'flex';
            jsonOutput.classList.remove('active');
            viewToggle.style.display = 'none';
            [copyBtn, downloadJsonBtn, downloadXmlBtn, downloadPdfBtn].forEach(btn => btn.disabled = true);
            currentOutput = null;
        } finally {
            // Restore UI
            btnText.style.display = 'inline';
            btnLoader.style.display = 'none';
            convertBtn.disabled = false;
        }
    });

    // --- Action Button Logic ---
    function renderOutput() {
        if (!currentOutput) return;
        if (currentView === 'json') {
            jsonOutput.textContent = JSON.stringify(currentOutput, null, 2);
        } else if (currentView === 'xml') {
            jsonOutput.textContent = currentOutput.results.map(r => r.xml || '').join('\n\n');
        }
    }

    toggleBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            toggleBtns.forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentView = e.target.getAttribute('data-view');
            renderOutput();
        });
    });

    copyBtn.addEventListener('click', () => {
        if (!jsonOutput.textContent) return;
        const textToCopy = jsonOutput.textContent;
        navigator.clipboard.writeText(textToCopy).then(() => {
            const originalIcon = copyBtn.innerHTML;
            copyBtn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>';
            setTimeout(() => { copyBtn.innerHTML = originalIcon; }, 2000);
        });
    });

    function submitNativeDownload(url, payloadObj) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = url;
        form.style.display = 'none';

        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'payload';
        input.value = JSON.stringify(payloadObj);

        form.appendChild(input);
        document.body.appendChild(form);
        form.submit();
        
        setTimeout(() => document.body.removeChild(form), 1000);
    }

    downloadJsonBtn.addEventListener('click', () => {
        if (!currentOutput) return;
        submitNativeDownload('/export/json', currentOutput);
    });

    downloadXmlBtn.addEventListener('click', () => {
        if (!currentOutput) return;
        submitNativeDownload('/export/xml', currentOutput);
    });

    downloadPdfBtn.addEventListener('click', () => {
        if (!currentOutput) return;
        submitNativeDownload('/export/pdf', currentOutput);
    });
});
