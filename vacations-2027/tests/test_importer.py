"""Fabricated documents only: no employee personal data in test fixtures."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from openpyxl import Workbook

from importer import MAX_FILE_SIZE, preview_import


class ImporterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def text(self, name, content):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def workbook(self, name, rows):
        path = self.root / name
        book = Workbook()
        for row in rows:
            book.active.append(row)
        book.save(path)
        book.close()
        return path

    def test_xlsx_selected_column_and_pdf_with_missing_spaces(self):
        selected = self.workbook("vacations.xlsx", [
            ["Врач", "Когда планируете работать?", "Январь"],
            ["Тестов"],
            ["Вымышленная"],
            [],
            ["Неизвестная"],
            ["Итого", 3],
            ["Отдел кадров"],
        ])
        names = self.text("names.pdf", "%PDF-fabricated")
        page = SimpleNamespace(extract_text=lambda: "# Фамилия Имя Отчество Дата рождения\n1 ТестовИван Петрович######## М login Врач\n2 Вымышленная АннаСергеевна######## Ж login Врач\n3 Лишний Пётр Олегович######## М login Врач\n4 ПроцедурныйПетра Метальникова proc1\n")
        with patch("pypdf.PdfReader", return_value=SimpleNamespace(pages=[page], is_encrypted=False)):
            result = preview_import(selected, names)
        self.assertEqual(result["counts"], {"selected": 3, "matched": 2, "unmatched": 1, "ambiguous": 0})
        self.assertEqual(result["matched"], [
            {"full_name": "Тестов Иван Петрович", "surname": "Тестов"},
            {"full_name": "Вымышленная Анна Сергеевна", "surname": "Вымышленная"},
        ])
        self.assertEqual(result["unmatched"], ["Неизвестная"])

    def test_shared_surname_is_ambiguous_and_not_fuzzy_matched(self):
        selected = self.text("vacations.txt", "Тестова\nТестоф\n")
        names = self.text("names.txt", "Тестова Анна Петровна\nТестова Мария Олеговна\nТестов Иван Петрович\n")
        result = preview_import(selected, names)
        self.assertEqual(result["matched"], [])
        self.assertEqual(result["unmatched"], ["Тестоф"])
        self.assertEqual(result["ambiguous"], [{"surname": "Тестова", "candidates": ["Тестова Анна Петровна", "Тестова Мария Олеговна"]}])

    def test_initials_disambiguate_but_do_not_override_mismatch(self):
        selected = self.text("vacations.txt", "Тестова М. О.\nТестов А. П.\n")
        names = self.text("names.txt", "Тестова Анна Петровна\nТестова Мария Олеговна\nТестов Иван Петрович\n")
        result = preview_import(selected, names)
        self.assertEqual(result["matched"], [{"full_name": "Тестова Мария Олеговна", "surname": "Тестова"}])
        self.assertEqual(result["unmatched"], ["Тестов А. П."])

    def test_exact_full_name_can_select_two_people_with_same_surname(self):
        selected = self.text("vacations.txt", "Тестова Анна Петровна\nТестова Мария Олеговна\n")
        names = self.text("names.txt", "Тестова Анна Петровна\nТестова Мария Олеговна\n")
        result = preview_import(selected, names)
        self.assertEqual(result["counts"]["matched"], 2)
        self.assertEqual(result["ambiguous"], [])

    def test_case_yo_and_duplicate_normalization(self):
        selected = self.text("vacations.txt", "тёстов\nТестов\nТЁСТОВ\n")
        names = self.text("names.txt", "Тестов Пётр Семёнович\nТЕСТОВ ПЕТР СЕМЕНОВИЧ\n")
        result = preview_import(selected, names)
        self.assertEqual(result["counts"], {"selected": 1, "matched": 1, "unmatched": 0, "ambiguous": 0})
        self.assertEqual(result["matched"][0]["full_name"], "Тестов Пётр Семёнович")

    def test_csv_headers_respect_column_order(self):
        selected = self.text("vacations.csv", "Отдел;Фамилия;Комментарии\nСклад;Тестова;любой текст\n")
        names = self.text("names.csv", "Должность;Имя;Отчество;Фамилия\nВрач;Анна;Петровна;Тестова\nВрач;Мария;Олеговна;Другая\n")
        result = preview_import(selected, names)
        self.assertEqual(result["matched"], [{"full_name": "Тестова Анна Петровна", "surname": "Тестова"}])

    def test_cp1251_csv_is_supported(self):
        selected = self.root / "vacations.csv"
        selected.write_bytes("Фамилия;Отдел\nТестов;Склад\n".encode("cp1251"))
        names = self.text("names.txt", "Тестов Иван Петрович\n")
        self.assertEqual(preview_import(selected, names)["counts"]["matched"], 1)

    def test_three_xlsx_name_columns_and_blank_row(self):
        selected = self.workbook("vacations.xlsx", [["Отдел", "Фамилия"], ["Склад", "Тестов"], [], ["Склад", "Вымышленная"]])
        names = self.workbook("names.xlsx", [["Фамилия", "Имя", "Отчество"], ["Тестов", "Иван", "Петрович"], ["Вымышленная", "Анна", "Сергеевна"]])
        self.assertEqual(preview_import(selected, names)["counts"]["matched"], 2)

    def test_docx_table(self):
        selected = self.text("vacations.txt", "Тестова\n")
        names = self.root / "names.docx"
        xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl>
        <w:tr><w:tc><w:p><w:r><w:t>Фамилия</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Имя</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Отчество</w:t></w:r></w:p></w:tc></w:tr>
        <w:tr><w:tc><w:p><w:r><w:t>Тестова</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Анна</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Петровна</w:t></w:r></w:p></w:tc></w:tr>
        </w:tbl></w:body></w:document>'''
        with ZipFile(names, "w") as archive:
            archive.writestr("word/document.xml", xml)
        self.assertEqual(preview_import(selected, names)["matched"], [{"full_name": "Тестова Анна Петровна", "surname": "Тестова"}])

    def test_repeat_aliases_are_one_employee(self):
        selected = self.text("vacations.txt", "Тестов\nТестов Иван Петрович\n")
        names = self.text("names.txt", "Тестов Иван Петрович\n")
        result = preview_import(selected, names)
        self.assertEqual(result["counts"]["selected"], 1)
        self.assertEqual(result["counts"]["matched"], 1)
        self.assertTrue(result["warnings"])

    def test_empty_or_invalid_source_has_useful_error(self):
        names = self.text("names.txt", "Тестов Иван Петрович\n")
        with self.assertRaisesRegex(ValueError, "пустой файл"):
            preview_import(self.text("empty.txt", ""), names)
        with self.assertRaisesRegex(ValueError, "не найдены фамилии"):
            preview_import(self.text("header.txt", "Отдел кадров\nВрач\nФамилия\n"), names)
        with self.assertRaisesRegex(ValueError, "не найдены полные ФИО"):
            preview_import(self.text("selected.txt", "Тестов\n"), self.text("no-names.txt", "Отдел кадров\n"))

    def test_unsupported_oversized_and_broken_files(self):
        names = self.text("names.txt", "Тестов Иван Петрович\n")
        with self.assertRaisesRegex(ValueError, "XLSX"):
            preview_import(self.text("bad.exe", "data"), names)
        big = self.root / "big.txt"
        with big.open("wb") as handle:
            handle.truncate(MAX_FILE_SIZE + 1)
        with self.assertRaisesRegex(ValueError, "10 МБ"):
            preview_import(big, names)
        with self.assertRaisesRegex(ValueError, "прочитать документ"):
            preview_import(self.text("broken.xlsx", "not a workbook"), names)

    def test_scanned_pdf_is_reported(self):
        selected = self.text("vacations.txt", "Тестов\n")
        names = self.text("names.pdf", "%PDF-fabricated")
        page = SimpleNamespace(extract_text=lambda: "")
        with patch("pypdf.PdfReader", return_value=SimpleNamespace(pages=[page], is_encrypted=False)):
            with self.assertRaisesRegex(ValueError, "нет распознаваемого текста"):
                preview_import(selected, names)

    def test_pdf_password_is_reported(self):
        selected = self.text("vacations.txt", "Тестов\n")
        names = self.text("names.pdf", "%PDF-fabricated")
        reader = SimpleNamespace(pages=[], is_encrypted=True, decrypt=lambda password: 0)
        with patch("pypdf.PdfReader", return_value=reader):
            with self.assertRaisesRegex(ValueError, "защищён паролем"):
                preview_import(selected, names)


if __name__ == "__main__":
    unittest.main()
