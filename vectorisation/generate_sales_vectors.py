import os
import numpy as np
import fitz
import torch
import cv2
import psycopg2
from PIL import Image
from transformers import CLIPProcessor, CLIPModel
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from transformers import BlipProcessor, BlipForConditionalGeneration
from moviepy.editor import VideoFileClip
from faster_whisper import WhisperModel

# === Configuration globale ===
PDF_DIR = "../docs/tutoring_docs"
IMAGE_DIR = "../docs/tutoring_docs/images"
VIDEO_DIR = "../docs/tutoring_docs/videos"

SUPABASE_CONFIG = {
    "host": "localhost",
    "port": 54322,
    "dbname": "postgres",
    "user": "postgres",
    "password": "postgres"
}

TABLE_NAME = "sales"  # table unique

# === Initialisation des modèles ===
text_embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/clip-ViT-B-32-multilingual-v1")
# clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
# clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-large")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-large")


# === PDF Processing ===
def extract_text_from_pdf(file_path):
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def process_pdfs(folder_path):
    all_chunks = []
    sources = []
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    for filename in os.listdir(folder_path):
        if filename.endswith(".pdf"):
            path = os.path.join(folder_path, filename)
            text = extract_text_from_pdf(path)
            chunks = text_splitter.split_text(text)
            all_chunks.extend(chunks)
            sources.extend([filename] * len(chunks))
    embeddings = text_embedding_model.embed_documents(all_chunks)
    return zip(embeddings, all_chunks, sources)  # ordre embedding, content, source


# === Image Processing ===
def generate_caption(image_path):
    raw_image = Image.open(image_path).convert('RGB')
    inputs = processor(raw_image, return_tensors="pt")
    out = model.generate(**inputs)
    caption = processor.decode(out[0], skip_special_tokens=True)
    return caption

def generate_embedding_image(folder_path):
    results = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            image_path = os.path.join(folder_path, filename)
            caption = generate_caption(image_path)
            vector = text_embedding_model.embed_query(caption)
            results.append((vector, caption, filename))
    return results


# === Video Processing ===
def extract_keyframes(video_path, every_n_frames=30):
    cap = cv2.VideoCapture(video_path)
    frames = []
    count = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        if count % every_n_frames == 0:
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            frames.append(img)
        count += 1
    cap.release()
    return frames

def extract_voice(video_path,audio_path="audio.wav"):
    clip=VideoFileClip(video_path)
    clip.audio.write_audiofile(audio_path,codec="pcm_s16le")
    return audio_path

whisper_model=WhisperModel("small", device="cpu")
def transcribe_audio(audio_path):
    segments, info = whisper_model.transcribe(audio_path, language="fr")
    transcript = " ".join([segment.text for segment in segments])
    return transcript

def process_video_audio(video_path):
    audio_path = extract_voice(video_path)
    transcript = transcribe_audio(audio_path)
    vector = text_embedding_model.embed_query(transcript)
    return vector, transcript

def process_videos(folder_path):
    results = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
            path = os.path.join(folder_path, filename)
            frames = extract_keyframes(path)
            captions = []
            for frame in frames:
                inputs = processor(frame, return_tensors="pt")
                out = model.generate(**inputs)
                caption = processor.decode(out[0], skip_special_tokens=True)
                captions.append(caption)
            vectors = text_embedding_model.embed_documents(captions)
            video_embedding = np.mean(vectors, axis=0)
            full_description = " ".join(captions)

            # Audio
            audio_vector, transcript = process_video_audio(path)
            combined_embedding = np.mean([video_embedding, np.array(audio_vector)], axis=0)

            # Résultats
            full_text = full_description + " " + transcript
            results.append((combined_embedding.tolist(), full_text, filename))
    return results


# === Insertion dans Supabase ===
def insert_embeddings_to_supabase(data, content_type):
    conn = psycopg2.connect(**SUPABASE_CONFIG)
    cur = conn.cursor()
    for embedding, content, source in data:
        cur.execute(
            f"""
            INSERT INTO {TABLE_NAME} (content, source, type, embedding)
            VALUES (%s, %s, %s, %s)
            """,
            (content, source, content_type, embedding)
        )
    conn.commit()
    cur.close()
    conn.close()


# === MAIN ===
if __name__ == "__main__":
    print("Traitement des PDFs...")
    pdf_data = process_pdfs(PDF_DIR)
    insert_embeddings_to_supabase(pdf_data, "pdf")

    print("Traitement des images...")
    image_data = generate_embedding_image(IMAGE_DIR)
    insert_embeddings_to_supabase(image_data, "image")

    print("Traitement des vidéos...")
    video_data = process_videos(VIDEO_DIR)
    insert_embeddings_to_supabase(video_data, "video")

    print("Tous les vecteurs ont été insérés dans Supabase.")
