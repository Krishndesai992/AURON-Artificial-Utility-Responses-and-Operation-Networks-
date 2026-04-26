import speech_recognition as sr
import getpass
import time

MAX_ATTEMPTS = 3

def authenticate_user():
    recognizer = sr.Recognizer()
    
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"\nAttempt {attempt} of {MAX_ATTEMPTS}")

        # === Voice Authentication First ===
        with sr.Microphone() as source:
            print("🔐 Say your passphrase or wait to type it...")
            try:
                audio = recognizer.listen(source, timeout=5)
                text = recognizer.recognize_google(audio).lower()
                if "unlock" in text:
                    print("✅ Voice recognized")
                    return True
                else:
                    print("❌ Voice did not match.")
            except:
                print("⚠️ Voice recognition failed or no input.")

        # === Fallback to password ===
        password = getpass.getpass("Enter password: ")
        if password == "openauron":
            print("✅ Password correct")
            return True
        else:
            print("❌ Incorrect password")

        time.sleep(1)

    print("🚫 Maximum attempts exceeded. Access denied.")
    return False
