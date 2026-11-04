# Default sprite sheet

`sprite_sheet.png` is the supplied 640 × 1024 character sheet, prepared with a transparent background. It is divided into eight rows of 64 × 128 frames. Rows 0, 2, 4, and 6 contain ten frames; rows 1, 3, 5, and 7 contain six frames, with the remaining cells blank.

The current window maps idle to row 4, listening to row 6, thinking to row 0, working to row 2, celebrate to row 5, confused to row 7, and talking to row 3. To replace the character, keep the same grid dimensions and frame counts, or update the grid constants and state-row map in `src/pet_window.py`.
