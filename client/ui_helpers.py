class ShakeAnimation:
    def __init__(self, duration=0.15, magnitude=5):
        self.active = False
        self.timer = 0.0
        self.duration = duration
        self.magnitude = magnitude

    def trigger(self):
        self.active = True
        self.timer = 0.0

    def update(self, dt):
        if not self.active:
            return
        self.timer += dt
        if self.timer > self.duration:
            self.active = False

    def get_offset(self):
        if not self.active:
            return 0
        phase = int(self.timer * 50)
        return int(self.magnitude * (-1 if phase % 2 == 0 else 1))


def format_time(total_seconds):
    secs = max(0, int(total_seconds))
    hours, rem = divmod(secs, 3600)
    mins, sec = divmod(rem, 60)
    return f"{hours:02d}:{mins:02d}:{sec:02d}"
