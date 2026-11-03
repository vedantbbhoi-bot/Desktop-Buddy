import soundfile as sf
import sounddevice as sd
data, fs = sf.read(io.BytesIO(wav_bytes))
sd.play(data, fs)
sd.wait()