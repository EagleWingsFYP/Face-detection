import argparse
import os
import time
import torch
import torch.nn as nn
import torchvision.transforms as transforms
import numpy as np
import cv2
import pickle
from .light_cnn import LightCNN_9Layers, LightCNN_29Layers, LightCNN_29Layers_v2

parser = argparse.ArgumentParser(description='PyTorch LightCNN Feature Extraction')
parser.add_argument('--arch', '-a', metavar='ARCH', default='LightCNN')
parser.add_argument('--cuda', '-c', default=False, action='store_true', help='Use CUDA if available')
parser.add_argument('--resume', default='F:\Python Project\LightCNN\LightCNN_29Layers_checkpoint.pth', type=str, metavar='PATH',
                    help='Path to the pre-trained checkpoint model')
parser.add_argument('--model', default='LightCNN-29', type=str, metavar='Model', help='Model type: LightCNN-9, LightCNN-29')
parser.add_argument('--root_path', default='F:\Python Project\eagle-wings-drone-project\tello\drone_project\data\dataset', type=str, metavar='PATH', 
                    help='Root path of face images.')
parser.add_argument('--save_path', default='F:\Python Project\eagle-wings-drone-project\tello\drone_project\data\extracted_features', type=str, metavar='PATH', 
                    help='Save path for extracted features.')
parser.add_argument('--num_classes', default=79077, type=int, metavar='N', help='Number of classes for the model.')  # FIXED

def detect_faces(image):
    """Detect faces in the input image using OpenCV Haar Cascade."""
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(image, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    return faces

def save_feature(save_path, person_name, img_name, features):
    """Save the extracted features for a face image."""
    person_dir = os.path.join(save_path, person_name)
    os.makedirs(person_dir, exist_ok=True)  # Create directory if it doesn't exist
    fname = os.path.splitext(os.path.join(person_dir, img_name))[0] + '.feat'
    try:
        with open(fname, 'wb') as fid:
            pickle.dump(features, fid)
        print(f"Saved features for {person_name}/{img_name} at {fname}")
    except Exception as e:
        print(f"Error saving features for {person_name}/{img_name}: {e}")

def main():
    args = parser.parse_args()

    # Load the model
    if args.model == 'LightCNN-9':
        model = LightCNN_9Layers(num_classes=args.num_classes)
    elif args.model == 'LightCNN-29':
        model = LightCNN_29Layers(num_classes=args.num_classes)
    elif args.model == 'LightCNN-29v2':
        model = LightCNN_29Layers_v2(num_classes=args.num_classes)
    else:
        raise ValueError(f"Invalid model type: {args.model}")

    # Load checkpoint
    if os.path.isfile(args.resume):
        print(f"Loading checkpoint from '{args.resume}'")
        checkpoint = torch.load(args.resume, map_location=torch.device('cpu'))
        state_dict = {k.replace('module.', ''): v for k, v in checkpoint['state_dict'].items()}
        model.load_state_dict(state_dict)
    else:
        raise FileNotFoundError(f"No checkpoint found at '{args.resume}'")

    model.eval()

    # Traverse through dataset folders
    for person_name in os.listdir(args.root_path):
        person_path = os.path.join(args.root_path, person_name)
        if not os.path.isdir(person_path):  # Skip files
            continue

        img_list = [f for f in os.listdir(person_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]
        if not img_list:
            print(f"No images found for {person_name} in {person_path}")
            continue

        print(f"Processing {len(img_list)} images for person: {person_name}")
        
        transform = transforms.Compose([transforms.ToTensor()])
        input_tensor = torch.zeros(1, 1, 128, 128)

        for img_name in img_list:
            img_path = os.path.join(person_path, img_name)
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)

            if img is None:
                print(f"Error reading image: {img_name}")
                continue

            faces = detect_faces(img)
            if len(faces) == 0:
                print(f"No faces detected in {img_name}")
                continue

            for (x, y, w, h) in faces:
                face = img[y:y+h, x:x+w]
                face_resized = cv2.resize(face, (128, 128))
                face_resized = np.reshape(face_resized, (128, 128, 1))
                face_resized = transform(face_resized)
                input_tensor[0, :, :, :] = face_resized

                start_time = time.time()
                with torch.no_grad():
                    _, features = model(input_tensor)
                elapsed_time = time.time() - start_time

                print(f"Processed {img_name} in {elapsed_time:.4f} seconds")
                save_feature(args.save_path, person_name, img_name, features.cpu().numpy()[0])

if __name__ == '__main__':
    main()
