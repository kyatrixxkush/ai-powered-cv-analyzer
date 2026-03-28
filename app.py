from flask import Flask, render_template, request, jsonify
import os
import PyPDF2
import pdfplumber
from openai import OpenAI
from io import BytesIO
import traceback

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"

# Create uploads folder if it doesn't exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def extract_text_from_pdf(file):
    """Extract text from PDF using PyPDF2"""
    try:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        
        if not text.strip():
            raise ValueError("No text could be extracted from the PDF")
        
        return text.strip()
    except Exception as e:
        raise Exception(f"PyPDF2 error: {str(e)}")

def extract_text_from_pdf_alternative(file):
    """Extract text using pdfplumber (more robust for complex PDFs)"""
    try:
        # Reset file pointer to beginning
        file.seek(0)
        file_content = file.read()
        pdf_file = BytesIO(file_content)
        
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        if not text.strip():
            raise ValueError("No text could be extracted from the PDF")
        
        return text.strip()
    except Exception as e:
        raise Exception(f"pdfplumber error: {str(e)}")

def extract_text_from_docx(file):
    """Extract text from DOCX file"""
    try:
        import docx
        file_content = file.read()
        doc = docx.Document(BytesIO(file_content))
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        
        if not text.strip():
            raise ValueError("No text could be extracted from the DOCX file")
        
        return text.strip()
    except Exception as e:
        raise Exception(f"DOCX error: {str(e)}")

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    error = None
    
    if request.method == "POST":
        try:
            # Validate inputs
            if "job_description" not in request.form or not request.form["job_description"].strip():
                error = "Job description is required"
                return render_template("index.html", result=None, error=error)
            
            if "cv" not in request.files:
                error = "CV file is required"
                return render_template("index.html", result=None, error=error)
            
            cv_file = request.files["cv"]
            job_desc = request.form["job_description"]
            
            # Check if file was selected
            if cv_file.filename == "":
                error = "No file selected"
                return render_template("index.html", result=None, error=error)
            
            # Check file extension
            file_extension = cv_file.filename.rsplit('.', 1)[-1].lower()
            
            # Extract text based on file type
            cv_text = None
            
            if file_extension == "pdf":
                try:
                    # Try PyPDF2 first
                    cv_text = extract_text_from_pdf(cv_file)
                except Exception as e:
                    # If PyPDF2 fails, try pdfplumber
                    print(f"PyPDF2 failed: {e}, trying pdfplumber...")
                    try:
                        cv_text = extract_text_from_pdf_alternative(cv_file)
                    except Exception as e2:
                        error = f"Failed to extract text from PDF: {str(e2)}"
                        return render_template("index.html", result=None, error=error)
            
            elif file_extension == "docx":
                try:
                    cv_text = extract_text_from_docx(cv_file)
                except Exception as e:
                    error = f"Failed to extract text from DOCX: {str(e)}"
                    return render_template("index.html", result=None, error=error)
            
            else:
                error = "Unsupported file format. Please upload PDF or DOCX files only."
                return render_template("index.html", result=None, error=error)
            
            # Check if text was extracted
            if not cv_text or not cv_text.strip():
                error = "Could not extract text from the uploaded file. The file might be empty or image-based."
                return render_template("index.html", result=None, error=error)
            
            # Create prompt for OpenAI
            prompt = f"""
Compare this CV with the job description. Be thorough and specific.

Job Description:
{job_desc}

CV:
{cv_text}

Please provide analysis in the following format:

**Score:** [X]% (where X is the match percentage)

**Missing Keywords:** 
- List important keywords from the job description that are missing in the CV
- Focus on skills, technologies, and qualifications

**Strengths:**
- What matches well in the CV

**Suggestions for Improvement:**
- Specific recommendations to improve the CV for this role
- What to add or emphasize

**Summary:**
Brief overall assessment
"""

            # Call OpenAI API
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are an expert CV analyzer and career coach. Provide detailed, actionable feedback."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            result = response.choices[0].message.content
            
            return render_template("index.html", result=result, error=None)
            
        except Exception as e:
            print(f"Unexpected error: {traceback.format_exc()}")
            error = f"An error occurred: {str(e)}"
            return render_template("index.html", result=None, error=error)
    
    return render_template("index.html", result=None, error=None)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)