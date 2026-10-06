"""Curriculum assembly.

Design rationale for the overall arc, recorded so it can be argued with:

Act I   builds the engine, because nothing else is comprehensible without it.
Act II  adds state, because every genuinely hard agent problem is a state
        problem - interruption, invariants, context limits.
Act III turns the engine into an application, which is where layering stops
        being an opinion and starts paying for itself.
Act IV  removes the scaffolding entirely.

Dependencies are declared per level rather than forcing one linear path, so a
learner who already understands the loop can branch straight to context
management without pretending otherwise.
"""

from __future__ import annotations

from academy.content_acts12 import act_one, act_two
from academy.content_systems import act_systems
from academy.content_acts34 import act_four, act_three
from academy.curriculum import Act


def build_acts() -> list[Act]:
    # Act II-B sits between state and the application layer: these are the
    # systems that surround the loop rather than constitute it.
    return [act_one(), act_two(), act_systems(), act_three(), act_four()]
