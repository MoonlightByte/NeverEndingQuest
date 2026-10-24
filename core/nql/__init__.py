# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Firelight engine bridge for the item ownership, equipment and armor class family.

The engine (Firelight, a separate Go program, ``bin/firelight-apply``) is the authority for who owns
what, who wears what, quantities, containers and derived armor class. This
package builds a world from existing character sheets, submits typed
transactions to the engine, and reads the engine's observations back. It never
parses prose and never computes a mechanical value itself.
"""
