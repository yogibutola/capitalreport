import pyttsx3

def text_to_speech(text: str):
    engine = pyttsx3.init()
    engine.setProperty("rate", 100)  # Speed of speech
    engine.setProperty("volume", 1.0)  # Volume (0.0 to 1.0)
    engine.say(text)
    engine.runAndWait()

if __name__ == "__main__":
    text = "Hello! This is a text to speech demo using Python."
    text_to_speech(text)
