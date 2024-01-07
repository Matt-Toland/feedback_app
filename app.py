import openai
import os
import json
from dotenv import load_dotenv
from pydub import AudioSegment
import tempfile
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# Load environment variables
load_dotenv()

# Instantiate OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")

# Define paths
recordings_path = 'feedback/mp4'
text_output_path = 'transcripts'
feedback_output_path = 'feedback_summary'
processed_files_list_path = 'processed_files.txt' 
processed_audio_list_path = 'processed_audio_files.txt' 
processed_feedback_list_path = 'processed_feedback_files.txt'  

# Define models and prompts
chatmodel = "gpt-3.5-turbo"  
with open("feedback_prompt.txt") as f:
     feedback_prompt = f.read()

# Firestore credentials
cred = credentials.Certificate("sylvi-feedbackk-firebase-adminsdk-foas2-c3ddcbb927.json")
firebase_admin.initialize_app(cred)

# Set up Firestore Connection
db = firestore.client()

def summarise_feedback(chatmodel, prompt, text):
    """
    Function to generate a summary using OpenAI's chat completions.
    """
    response = openai.chat.completions.create(
        model=chatmodel,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ]
    )
    
    problem_statement = response.choices[0].message.content
    return problem_statement

def split_audio(file_path, max_size_in_bytes=26213400):
    """
    Function to split audio file into smaller chunks.
    """
    audio = AudioSegment.from_file(file_path)
    chunk_length_ms = int((max_size_in_bytes / len(audio)) * 1000)
    return [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]

def read_file(file_path):
    """
    Function to read a file and return its content.
    """
    with open(file_path, 'r') as file:
        return file.read()

def write_file(content, file_path):
    """
    Function to write content to a file.
    """
    with open(file_path, 'w') as file:
        file.write(content)

def parse_feedback(file_content):
    """
    Parses the structured feedback from the given file content and returns it as a list of dictionaries.
    """
    feedback_entries = []
    for line in file_content.split("\n"):
        if line.startswith("Feedback:"):
            parts = line.split(";")
            feedback_info = {}
            for part in parts:
                key, value = part.split(":")[0].strip(), part.split(":")[1].strip()
                feedback_info[key.lower()] = value
            feedback_entries.append(feedback_info)
    return feedback_entries

def add_user_feedback(user_id, feedback, category, priority):
    """
    Function to write user feedback to firestore db.
    """    
    
    feedback_data = {
        "user_id": user_id,
        "feedback": feedback,
        "category": category,
        "priority": priority,
        "timestamp": firestore.SERVER_TIMESTAMP  # Automatically set server timestamp
    }

    # Add a new document in the 'feedback' collection
    db.collection('feedback').document().set(feedback_data)

def read_processed_files_list(file_path):
    """
    Function to read in the list of file names already processed
    """   
   
    try:
        with open(file_path, 'r') as file:
            return file.read().splitlines()
    except FileNotFoundError:
        return []

def add_to_processed_files_list(file_path, filename):
    """
    Function to write processed file name to records
    """   
    
    with open(file_path, 'a') as file:
        file.write(filename + '\n')


# Ensure the output directories exist
if not os.path.exists(text_output_path):
    os.makedirs(text_output_path)

if not os.path.exists(feedback_output_path):
    os.makedirs(feedback_output_path)


# Read the list of already processed audio files
processed_audio_files = read_processed_files_list(processed_audio_list_path)

# Process each audio file
for filename in os.listdir(recordings_path):
    if filename.endswith('.mp4') and filename not in processed_audio_files:  # Process only new mp4 files
        full_transcript = ""
        audio_chunks = split_audio(os.path.join(recordings_path, filename))

        for chunk in audio_chunks:
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                chunk.export(temp_file.name, format="mp3")
                with open(temp_file.name, "rb") as audio_file:
                    transcript_part = openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        response_format='text'
                    )
                    # Assuming the response is a dictionary with a 'text' key
                    full_transcript += transcript_part

        # Save the combined transcript and update processed list
        transcript_file_path = os.path.join(text_output_path, filename.split('.')[0] + '.txt')
        write_file(full_transcript, transcript_file_path)
        add_to_processed_files_list(processed_audio_list_path, filename)

# Read the list of already processed feedback files
processed_feedback_files = read_processed_files_list(processed_feedback_list_path)

# Process each transcript file and generate feedback summary
for filename in os.listdir(text_output_path):
    if filename.endswith('.txt') and filename not in processed_feedback_files:
        file_path = os.path.join(text_output_path, filename)
        meetingtext = read_file(file_path)
        problem_statement = summarise_feedback(chatmodel, feedback_prompt, text=meetingtext)

        # Create output file name with date
        output_filename = f"{filename.split('.')[0]}_{datetime.now().strftime('%Y%m%d')}.txt"
        output_file_path = os.path.join(feedback_output_path, output_filename)

        # Write the summary to the new file and update processed list
        write_file(problem_statement, output_file_path)
        print(f"Processed {filename} and saved summary to {output_filename}")
        add_to_processed_files_list(processed_feedback_list_path, filename)


# Read the list of already processed files
processed_files = read_processed_files_list(processed_files_list_path)

# Check for new feedback files and process them
for filename in os.listdir(feedback_output_path):
    if filename.endswith('.txt') and filename not in processed_files:
        file_path = os.path.join(feedback_output_path, filename)
        with open(file_path, 'r') as f:
            file_content = f.read()
            feedback_entries = parse_feedback(file_content)
            for entry in feedback_entries:
                add_user_feedback(
                    user_id=entry.get('user_id', 'default_user'),
                    feedback=entry.get('feedback', ''),
                    category=entry.get('category', ''),
                    priority=entry.get('priority', '')
                )
                print(f"Added feedback to Firestore: {entry}")
                # Mark this file as processed
            add_to_processed_files_list(processed_files_list_path, filename)
            print(f"Processed and added {filename} to Firestore")