import asyncio
import threading

from preferans.online.publish_signal import PublishSignal, wait_for_publish_or_frame


def test_room_isolation_and_unsubscribe():
    signal = PublishSignal()
    called = []
    unsubscribe = signal.subscribe("a", lambda: called.append("a"))
    other = signal.subscribe("b", lambda: called.append("b"))
    signal.notify("a")
    assert called == ["a"]
    unsubscribe()
    unsubscribe()
    signal.notify("a")
    signal.notify("b")
    assert called == ["a", "b"]
    other()
    assert signal._listeners == {}


def test_thread_publish_wakes_without_waiting_for_frame():
    async def scenario():
        signal = PublishSignal()
        event = asyncio.Event()
        loop = asyncio.get_running_loop()
        unsubscribe = signal.subscribe("room", lambda: loop.call_soon_threadsafe(event.set))
        reader = asyncio.create_task(asyncio.sleep(2))
        thread = threading.Thread(target=signal.notify, args=("room",))
        thread.start()
        thread.join()
        try:
            assert not await wait_for_publish_or_frame(reader, event)
            assert event.is_set()
            assert not reader.done()
        finally:
            unsubscribe()
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)

    asyncio.run(scenario())


def test_frame_is_not_lost_when_publish_and_frame_are_ready():
    async def scenario():
        event = asyncio.Event()
        event.set()
        reader = asyncio.create_task(asyncio.sleep(0, result="frame"))
        await reader
        assert await wait_for_publish_or_frame(reader, event)
        assert reader.result() == "frame"

    asyncio.run(scenario())
