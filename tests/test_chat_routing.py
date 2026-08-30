from __future__ import annotations

import unittest

from app.main import _chat_general_answer, _is_general_chat_message, _should_use_general_chat


class ChatRoutingTests(unittest.TestCase):
    def test_application_capability_questions_do_not_use_rag(self) -> None:
        for message in (
            "RaporHub ne yapar?",
            "RepOcto ne yapar?",
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

    def test_short_thanks_use_general_chat_even_in_report_mode(self) -> None:
        for message in ("sağol", "teşekkürler", "eyvallah"):
            with self.subTest(message=message):
                self.assertTrue(_should_use_general_chat("report", message))

        self.assertFalse(
            _should_use_general_chat("report", "2025-BIG-E-DUR-01 raporunun sonucu nedir?")
        )
        self.assertEqual(("Rica ederim.", "chat-direct", 1.0), _chat_general_answer("sağol"))


if __name__ == "__main__":
    unittest.main()
