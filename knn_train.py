import os
import cv2
import numpy as np
from sklearn.neighbors import KNeighborsClassifier
from sklearn.utils import shuffle
import joblib

# Load dataset
def load_data(folder):
    X, y = [], []
    for label in os.listdir(folder):
        label_path = os.path.join(folder, label)
        if not os.path.isdir(label_path):
            continue
        for img_file in os.listdir(label_path):
            img_path = os.path.join(label_path, img_file)
            img = cv2.imread(img_path)
            if img is None:
                continue
            img = cv2.resize(img, (64, 64))
            img = img / 255.0  # normalize pixels (match with app.py)
            img = img.flatten()
            X.append(img)
            y.append(label.lower())  # standardize labels to lowercase
    return np.array(X), np.array(y)

print("Loading training data...")
X_train, y_train = load_data("dataset/train")

# Shuffle data so classes are mixed
X_train, y_train = shuffle(X_train, y_train, random_state=42)

# Print dataset balance
unique, counts = np.unique(y_train, return_counts=True)
print("Class distribution:", dict(zip(unique, counts)))

print("Training KNN...")
model = KNeighborsClassifier(
    n_neighbors=3,         # you can tune this
    weights='distance',    # closer points have more weight
    metric='manhattan'     # better for pixel data
)
model.fit(X_train, y_train)

print("Saving model...")
joblib.dump(model, "model_knn.pkl")
print("Done.")
