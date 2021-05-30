"""
Constants for the connection.

Used in .process and .communicate.
"""


#PICK_STROKE_MESSAGE="pick"

PICK_BUTTON_MESSAGE="pick_button"
"""
Sent from child to parent
Parameter: Optional[Entry]
(None if the user closed the window without picking an entry)
"""


EXIT_MESSAGE="exit"
"""
Sent from parent to child
Parameters: none
The subprocess should exit
"""

#CLOSE_WINDOW_MESSAGE="close_window"



ADD_TRANSLATION_MESSAGE="add_translation"
"""
The subprocess should send (ADD_TRANSLATION_MESSAGE, <Entry>) to the parent process.
"""

REMOVE_TRANSLATION_MESSAGE="remove_translation"
"""
The subprocess should send (REMOVE_TRANSLATION_MESSAGE, <Entry>) to the parent process.
"""

SEARCH_MESSAGE="search"
"""
The subprocess should send (SEARCH_MESSAGE, query: str) to the parent process.

Then the parent process should respond with (SEARCH_MESSAGE, List[Entry]).
"""

OPEN_DIALOG_MESSAGE="open_dialog"
"""
The parent process should send (OPEN_DIALOG_MESSAGE, None) to the child process.
"""

SHOW_ERROR_MESSAGE="show_error"
"""
The child process should send a message to the parent process to show an error message.
"""

