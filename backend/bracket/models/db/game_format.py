from enum import StrEnum


class GameFormat(StrEnum):
    """
    NFF game formats ("spilleformer"); smaller formats are played on parts of a full pitch.
    """

    THREE_A_SIDE = "3v3"
    FIVE_A_SIDE = "5v5"
    SEVEN_A_SIDE = "7v7"
    NINE_A_SIDE = "9v9"
    ELEVEN_A_SIDE = "11v11"
