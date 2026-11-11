__all__ = ["start", "router"]


def start():
    from devsim.devices import SimulatedScanner, SimulatedSensor
    import core.kiosk as kiosk

    return kiosk.start_simulator(SimulatedScanner(), SimulatedSensor())


def router():
    from devsim.routes import router as simulator_router

    return simulator_router
