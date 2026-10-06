"""Async in three minutes.

Run this before Level 2's implementation steps. It exists because the agent
loop is an *async generator*, and that is two unfamiliar ideas stacked on top
of each other. Separating them here means the loop itself is the only new
thing later.
"""

from __future__ import annotations

import asyncio

DIM, BLUE, GREEN, YELLOW, RESET = "\033[2m", "\033[94m", "\033[92m", "\033[93m", "\033[0m"


def heading(text: str) -> None:
    print(f"\n{BLUE}{'─' * 60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'─' * 60}{RESET}")


# ---------------------------------------------------------------- 1

def normal_function() -> list[str]:
    """Computes everything, then hands back one value. You wait for all of it."""
    return ["first", "second", "third"]


# ---------------------------------------------------------------- 2

def generator():
    """Hands back values one at a time, pausing in between.

    `yield` means: give the caller this value now, and remember where I was.
    """
    print(f"{DIM}    (generator: about to yield 'first'){RESET}")
    yield "first"
    print(f"{DIM}    (generator: resumed, now yielding 'second'){RESET}")
    yield "second"
    print(f"{DIM}    (generator: resumed, now yielding 'third'){RESET}")
    yield "third"


# ---------------------------------------------------------------- 3

async def async_generator():
    """Same as above, but it can *wait* between yields without blocking.

    This is the shape of every agent loop: produce a value, wait for the
    network, produce another value.
    """
    for word in ["first", "second", "third"]:
        await asyncio.sleep(0.25)          # pretend this is a network call
        yield word


# ---------------------------------------------------------------- 4

async def who_does_the_work():
    """A generator does nothing until someone iterates it.

    This matters in Level 5. Calling a function that returns an async
    generator does not run any of its body.
    """
    print(f"{YELLOW}    body is running NOW{RESET}")
    yield "value"


async def main() -> None:
    heading("1. A normal function: one return, you wait for everything")
    print(f"  result = {normal_function()}")

    heading("2. A generator: many values, one at a time")
    print("  for word in generator():")
    for word in generator():
        print(f"      got {GREEN}{word}{RESET}")
    print(f"\n  {DIM}Notice the interleaving: the generator runs a bit, pauses,{RESET}")
    print(f"  {DIM}your loop body runs, then the generator resumes.{RESET}")

    heading("3. An async generator: many values, and it can wait in between")
    print("  async for word in async_generator():")
    async for word in async_generator():
        print(f"      got {GREEN}{word}{RESET}  {DIM}(waited 0.25s first){RESET}")
    print(f"\n  {DIM}Two keywords, two jobs:{RESET}")
    print(f"  {DIM}  await     = pause here until this finishes{RESET}")
    print(f"  {DIM}  yield     = hand a value to whoever is looping over me{RESET}")
    print(f"  {DIM}  async for = the loop you use to consume one of these{RESET}")

    heading("4. Nothing runs until you iterate")
    print("  stream = who_does_the_work()      <- body has NOT run")
    stream = who_does_the_work()
    print(f"  {DIM}...still nothing...{RESET}")
    print("  async for value in stream:        <- NOW it runs")
    async for value in stream:
        print(f"      got {GREEN}{value}{RESET}")

    print(f"\n{BLUE}{'─' * 60}{RESET}")
    print("That is the whole language feature.")
    print("")
    print("Your agent loop will be an async generator because it has to do")
    print("exactly these two things, repeatedly:")
    print(f"  {GREEN}await{RESET}  the model's response (slow, network)")
    print(f"  {GREEN}yield{RESET}  an event so the UI can show progress immediately")
    print("")
    print("If it only returned at the end, nothing could render until the")
    print("entire run finished.")
    print("")


if __name__ == "__main__":
    asyncio.run(main())
