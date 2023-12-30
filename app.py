import openai 
import os
from dotenv import load_dotenv
from pydub import AudioSegment
import tempfile 


# Load environment variables
load_dotenv()

# Instantiate OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")
print("API Key:", os.getenv("OPENAI_API_KEY"))
#client = OpenAI(api_key=openaiapikey)

# Define paths
recordings_path = 'feedback/mp4'
output_path = 'output/audio_transcripts'

# Check and create the output directory if it does not exist
if not os.path.exists(output_path):
    os.makedirs(output_path)

def split_audio(file_path, max_size_in_bytes=26213400):  # Adjust the size limit as needed
    audio = AudioSegment.from_file(file_path)
    chunk_length_ms = int((max_size_in_bytes / len(audio)) * 1000)  # Duration of each chunk in milliseconds
    return [audio[i:i + chunk_length_ms] for i in range(0, len(audio), chunk_length_ms)]

# Process each audio file
filenames = [filename for filename in os.listdir(recordings_path) if os.path.isfile(os.path.join(recordings_path, filename))]
for filename in filenames:
    full_transcript = ""

    audio_chunks = split_audio(os.path.join(recordings_path, filename))
    for chunk in audio_chunks:
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:  # Save each chunk to a temporary file
            chunk.export(temp_file.name, format="mp3")
            with open(temp_file.name, "rb") as audio_file:
                transcript_part = openai.audio.transcriptions.create(
                    model="whisper-1", 
                    file=audio_file,
                    response_format='text'
                )
                # Check if the response is a string or a dictionary
                if isinstance(transcript_part, dict):
                    # If it's a dictionary, append the 'text' field
                    full_transcript += transcript_part['text']
                else:
                    # If it's a string, append it directly
                    full_transcript += transcript_part

    # Save the combined transcript
    with open(os.path.join(output_path, filename.split('.')[0] + '.txt'), 'w') as f:
        f.write(full_transcript)


