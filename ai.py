import google.generativeai as genai
import os

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def analyze_complaint_with_gemini(text):
    model = genai.GenerativeModel("gemini-1.5-flash")
    prompt = f"Is civic complaint ko analyze karo. Category, priority (High/Medium/Low) aur summary batao: {text}"
    response = model.generate_content(prompt)
    return {"analysis": response.text}