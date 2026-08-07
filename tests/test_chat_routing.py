from __future__ import annotations

import unittest

from app.main import _is_general_chat_message


class ChatRoutingTests(unittest.TestCase):
    def test_application_capability_questions_do_not_use_rag(self) -> None:
        for message in (
            "RaporHub ne yapar?",
            "SmartCAE AI ne yapar?",
            "Bu uygulama ne yapar?",
            "Kendinden bahset",
        ):
            with self.subTest(message=message):
                self.assertTrue(_is_general_chat_message(message))

    def test_report_questions_still_use_rag(self) -> None:
        for message in (
            "BIG-E konfor raporunda hangi parkurlar var?",
            "2025-BIG-E-DUR-01 raporunun sonucu nedir?",
        ):
            with self.subTest(message=message):
                self.assertFalse(_is_general_chat_message(message))


if __name__ == "__main__":
    unittest.main()
