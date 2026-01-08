import cv2
import time

print("--- TESTING CAMERA ---")

try:
    # Initialize camera (0 is usually the default Pi Camera)
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ Error: Could not open camera. Check ribbon cable connection.")
        exit()

    print("✅ Camera initialized.")
    print("Warming up camera for 2 seconds...")
    time.sleep(2)

    # Read a frame
    ret, frame = cap.read()

    if ret:
        filename = "test_image.jpg"
        cv2.imwrite(filename, frame)
        print(f"✅ Success! Image saved as '{filename}'.")
        print("Check your file manager to view the image.")
    else:
        print("❌ Error: Failed to capture image.")

    # Release the camera
    cap.release()

except Exception as e:
    print(f"❌ Error: {e}")