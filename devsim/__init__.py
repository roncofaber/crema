__all__ = ["start", "router"]


def start():
    from devsim.devices import SimulatedScanner, SimulatedSensor
    import core.kiosk as kiosk

    return kiosk.start_simulator(SimulatedScanner(), SimulatedSensor())


def router():
    from fastapi import APIRouter
    from devsim.routes import panel_router, router as simulator_router

    combined = APIRouter()
    combined.include_router(simulator_router)
    combined.include_router(panel_router)
    return combined
