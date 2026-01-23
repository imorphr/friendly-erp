import frappe


class ProgressNotifier:
    def init(self, total_steps: int, title: str) -> None:
        pass

    def step(self, current_step: int, message: str) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def done(self) -> None:
        pass


class ConcreteProgressNotifier(ProgressNotifier):
    def __init__(self):
        self.total_steps: int = 0
        self.title: str = ""

    def init(self, total_steps: int, title: str) -> None:
        self.total_steps = total_steps
        self.title = title

        frappe.publish_progress(
            0,
            title=self.title,
            description="Initializing"
        )

    def step(self, current_step: int, message: str) -> None:
        percent = int((current_step / self.total_steps)
                      * 100) if self.total_steps else 100

        frappe.publish_progress(
            percent,
            title=self.title,
            description=message
        )

    def info(self, message: str) -> None:
        frappe.publish_progress(
            None,
            title=self.title,
            description=message
        )

    def done(self) -> None:
        frappe.publish_progress(
            100,
            title=self.title,
            description="Completed"
        )

class NullProgressNotifier(ProgressNotifier):
    def init(self, total_steps: int, title: str) -> None:
        pass

    def step(self, current_step: int, message: str) -> None:
        pass

    def info(self, message: str) -> None:
        pass

    def done(self) -> None:
        pass