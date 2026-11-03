# in src/intent_router.py, on the main thread
from PySide6.QtCore import QThreadPool, QRunnable

class _SpeakTask(QRunnable):
    def __init__(self, tts, text):
        super().__init__()
        self._tts, self._text = tts, text
    def run(self):
        self._tts.speak(self._text)

QThreadPool.globalInstance().start(_SpeakTask(self.tts, reply_text))