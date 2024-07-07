# extract resume data
from langchain_community.llms import Ollama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers import BaseOutputParser
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv


from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from uuid import uuid4
import datetime, PyPDF2, os, docx, io
from supabase import create_client, Client
# from exceptions import PendingDeprecationWarning


import warnings
warnings.simplefilter('ignore', PendingDeprecationWarning)

load_dotenv()

api_key = os.getenv('OPEN_API_KEY')
supabase_url = os.getenv('SUPABASE_URL')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

llm2 = ChatOpenAI(openai_api_key=api_key)
llm = Ollama(model="llama2")



def extract_resume_text(file_content):
  """
  Extracts text from a PDF file in memory using PyPDF2.

  Args:
      file_content: The PDF file content in bytes.

  Returns:
      Extracted text as a string.
  """
  
  from PyPDF2 import PdfReader

  with io.BytesIO(file_content) as pdf_file:
    pdf_reader = PdfReader(pdf_file)
    text = ""
    for page_num in range(len(pdf_reader.pages)):
      page = pdf_reader.pages[page_num]
      text += page.extract_text()
  return text


# job requirement


# create a prompt
def tailored_resume(myresume : str, jobdescription : str):

    SYSTEM_TEMPLATE = """
    I have my existing resume and the job description for a job am interested in.

    Using my resume, please generate a new, tailored resume that highlights my most relevant skills and experiences  for this specific job opening.

    Here's my existing resume:

    {my_resume}

    Here's the job description for the position am interested in:

    {job_description}

    In the new, tailored resume,  focus on:

    Emphasizing the skills and experience listed in the job description that match my qualifications.
    Quantifying my achievements with numbers and metrics whenever possible.
    Highlighting relevant responsibilities from my past experiences that demonstrate my ability to perform the duties mentioned in the job description.
    Using keywords from the job description throughout the resume, especially in the summary/objective, work experience, and skills sections.
    Please maintain a clear and concise format, ideally keeping the resume to one page unless my experience is highly relevant to the specific job

    
    """

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system",SYSTEM_TEMPLATE)
        ]
    )

    output_parser = StrOutputParser()

    chain = prompt | llm2 | output_parser

    response = chain.invoke(
    
        {
           'my_resume': myresume,
           'job_description': jobdescription,
           
       
    })

    return response


def write_to_docx(tailord_resume_response, filename):
  doc = docx.Document()

  # Add your generated output to the document
  paragraph = doc.add_paragraph(tailord_resume_response)  # Add as a paragraph

  # Save the document
  doc.save(filename)

# Write the data to a Word document
# write_to_docx(tailord_resume_response, "testresume.docx")



def main():
  # Example usage
    # pdf_text = extract_resume_text("JohnSaidi.pdf")
    # print(pdf_text)

    # import jobd
    # jd = jobd.requirements

    # print(jd)

    # tailored_resume_response = tailored_resume(pdf_text, jd)
    # write_to_docx(tailored_resume_response, "resume2.docx")
  
  
  # res = supabase.storage.list_buckets()
  # supabase.storage.from_("resumes").upload('1q2w3e4r5t6y', "JohnSaidi.pdf")

  # res = supabase.storage.get_bucket("resumes")
  # print('upload complete')
  # print(test_database)

  extracted_text = supabase.table('resume_data').select('extractedresume_data').eq('resume_uid', '00f4276d-8498-4c88-8f02-f541996d61d0').execute()
  print(extracted_text.data[0])


app = FastAPI()


ALLOWED_EXTENSIONS = {"pdf", "docx"}  # Allowed file extensions for resume uploads

def validate_file(filename: str):
  """Checks if the filename extension is allowed."""
  file_extension = os.path.splitext(filename)[1][1:].lower()
  return file_extension in ALLOWED_EXTENSIONS

@app.post("/api/v1/upload_resume")
async def upload_resume(file: UploadFile = File(...)):
  """Uploads a user's resume to Supabase storage."""

  # Check if a file was uploaded
  if not file:
    raise HTTPException(status_code=400, detail="No file uploaded")

  # Validate file extension
  if not validate_file(file.filename):
    raise HTTPException(status_code=400, detail="Invalid file format. Allowed extensions: pdf, docx")

  # Generate a unique identifier for the uploaded resume
  resume_id =  f"original_resume_{str(uuid4())}.pdf"

  try:
    file_content = await file.read()

    # Extract text from the uploaded file content
    extracted_text = extract_resume_text(file_content)

    # Upload the file to Supabase storage
    supabase.storage.from_("resumes").upload(resume_id, file_content)

    # Save resume data to Supabase table
    supabase.table("resume_data").insert({"resume_uid": resume_id, "extractedresume_data": extracted_text}).execute()

  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Error saving uploaded file: {e}")

  # Return success response with details
  return {
    "status": "success",
    "message": "File uploaded successfully to Supabase storage.",
    "data": {
      "id": resume_id,
      "filename": file.filename,
      "upload_date": datetime.datetime.utcnow().isoformat()
    }
  }


@app.post("/api/v1/resume/{resumeId}/tailored")
async def tailored(resumeID: str, job_description: str = Form(...)):

  # Check if job description are provided
  if not job_description:
      raise HTTPException(status_code=400, detail="Job title and description are required")
  
  try:
      # get extracted resume data based on the resume id
      extracted_text_response = supabase.table('resume_data').select('extractedresume_data').eq('resume_uid', resumeID).execute()
      # print(extracted_text.data[0])
      # create the tailored resume
      if not extracted_text_response.data:
        raise HTTPException(status_code=404, detail="Resume data not found for provided ID")
      
      tailored_r = tailored_resume(extracted_text_response.data[0], job_description)
      # print(tailored_r)

      try:
            # Create a BytesIO object for the generated docx
            tailored_resume_bytes = io.BytesIO()

            # create a word document
            tailored_resume_docx = write_to_docx(tailored_r, tailored_resume_bytes)

            # Generate a unique identifier for the uploaded resume
            tailoredresume_id = f"tailored_resume_{str(uuid4())}.docx"

            # Upload the file to Supabase storage / bucket
            supabase.storage.from_("tailored_resumes").upload(tailoredresume_id, tailored_resume_bytes.getvalue())
            tailored_resume_bytes.close()

            # Save resume data to Supabase table
            # supabase.table("resume_data").insert({"resume_uid": tailoredresume_id, "extractedresume_data": extracted_text}).execute()

            return {
                    "status": "success",
                    "message": "Tailored resume succesfully created.",
                    "data": {"tailored id": tailoredresume_id}
          }
           

      except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error uploaded the tailored resume: {e}")
        
  except HTTPException as e:
        raise e     
  except Exception as e:
      raise HTTPException(status_code=500, detail=f"Error generating tailored resume: {e}")



@app.post("/api/v1/{resumeID}/download")
async def upload_job_requirements(resumeID :str):
    pass

if __name__ == "__main__":
   main()