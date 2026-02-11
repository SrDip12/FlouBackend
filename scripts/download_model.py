from sentence_transformers import SentenceTransformer
import os

def download_model():
    print("Downloading model for Docker build...")
    # Explicitly set cache folder if needed, or rely on default
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Model downloaded successfully.")

if __name__ == "__main__":
    download_model()
