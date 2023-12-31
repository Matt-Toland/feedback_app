import openai
import os
from dotenv import load_dotenv
from pydub import AudioSegment
import tempfile
from datetime import datetime

# Load environment variables
load_dotenv()

# Instantiate OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")

# Define paths
recordings_path = 'feedback/mp4'
text_output_path = 'transcripts'
feedback_output_path = 'feedback_summary'

# Define models and prompts
chatmodel = "gpt-3.5-turbo"  
feedback_prompt = "Please read the provided user feedback and categorize each point into one of the following categories: ..."

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

# Ensure the output directories exist
if not os.path.exists(text_output_path):
    os.makedirs(text_output_path)

if not os.path.exists(feedback_output_path):
    os.makedirs(feedback_output_path)

# Process each audio file
for filename in os.listdir(recordings_path):
    if filename.endswith('.mp4'):  # Process only mp4 files
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

        # Save the combined transcript
        transcript_file_path = os.path.join(text_output_path, filename.split('.')[0] + '.txt')
        write_file(full_transcript, transcript_file_path)

# Process each transcript file and generate feedback summary
for filename in os.listdir(text_output_path):
    if filename.endswith('.txt'):
        file_path = os.path.join(text_output_path, filename)
        meetingtext = read_file(file_path)
        problem_statement = summarise_feedback(chatmodel, feedback_prompt, text=meetingtext)

        # Create output file name with date
        output_filename = f"{filename.split('.')[0]}_{datetime.now().strftime('%Y%m%d')}.txt"
        output_file_path = os.path.join(feedback_output_path, output_filename)

        # Write the summary to the new file
        write_file(problem_statement, output_file_path)
        print(f"Processed {filename} and saved summary to {output_filename}")
