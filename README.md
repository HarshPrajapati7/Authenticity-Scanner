# Document Trust Engine

Document Trust Engine is a multi-modal document authenticity and forgery detection platform designed to evaluate the trustworthiness of digital content across text, documents, images, video, and audio. The system combines traditional forensic analysis techniques with modern machine learning models to identify indicators of manipulation, synthetic generation, and potential fraud.

The platform is implemented using a decoupled architecture consisting of a Next.js frontend and a FastAPI backend. An asynchronous job-processing workflow enables scalable analysis by separating user requests from computationally intensive forensic operations. Uploaded content is validated, routed through modality-specific analysis pipelines, and consolidated into a unified forensic report.

The system supports analysis of plain text, PDF documents, images, videos, and audio files. For textual content, AI-generated text detection is performed using transformer-based language models, complemented by linguistic consistency analysis and heuristic evaluation. PDF documents undergo structural parsing, text extraction, and embedded image inspection, allowing forensic evidence to be gathered from both visual and textual components.

Image analysis combines metadata examination with visual forensic techniques including Error Level Analysis (ELA), Fast Fourier Transform (FFT) frequency analysis, and Laplacian-based noise assessment. Deepfake and synthetic image detection are performed using Vision-Language Models (VLMs), enabling identification of AI-generated visual artifacts that may not be detectable through traditional methods alone. Security-oriented checks further evaluate document integrity through QR-code validation, seal verification, and document consistency assessment.

Video and audio files are processed through integrity-based forensic pipelines that evaluate structural characteristics and metadata consistency. The architecture is designed to support future integration of advanced deepfake classification models for richer multimedia analysis.

To improve interpretability, the platform generates explainable forensic reports containing confidence scores, detected anomalies, supporting evidence, and visual heatmaps highlighting suspicious regions. Individual forensic signals are aggregated through a weighted scoring framework to produce an overall fraud confidence score ranging from 0 to 100. Based on this score, the system classifies content as Genuine, Suspicious, or Likely Forged.

The platform has been engineered for cloud deployment and supports both local model execution and remote inference through Hugging Face APIs. Containerized deployment using Docker enables reproducible execution across development and production environments. The modular architecture further allows future extensions such as OCR integration, database-backed persistence, audit logging, and model fine-tuning on domain-specific forgery datasets.

By combining machine learning, computer vision, digital forensics, and explainable AI techniques within a unified framework, Document Trust Engine provides a comprehensive solution for assessing digital document authenticity and detecting potential manipulation across multiple content modalities.
