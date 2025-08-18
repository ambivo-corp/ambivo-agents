# ambivo_agents/services/file_processor.py
"""
Comprehensive file processing service for various file formats
Supports: Excel, CSV, Word, PDF, PowerPoint, JSON, Images, and generic text files
"""

import json
import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    import pypdf

    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    from docx import Document as DocxDocument

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from pptx import Presentation

    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

try:
    from PIL import Image

    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

try:
    import pytesseract

    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from llama_index.core import SimpleDirectoryReader, Document
from llama_index.core.readers import Document as LIDoc


class FileProcessorService:
    """
    Service for processing various file types and converting them to indexable documents
    """

    def __init__(self):
        self.logger = logging.getLogger(f"FileProcessorService")
        self.supported_extensions = {
            # Spreadsheets
            "xlsx",
            "xls",
            # Documents
            "doc",
            "docx",
            "pdf",
            "txt",
            "md",
            "rtf",
            # Presentations
            "ppt",
            "pptx",
            # Data formats
            "csv",
            "json",
            "jsonl",
            "xml",
            # Images
            "png",
            "jpg",
            "jpeg",
            "gif",
            "bmp",
            "tiff",
            "webp",
            # Code files
            "py",
            "js",
            "html",
            "css",
            "java",
            "cpp",
            "c",
            "php",
            "rb",
            "go",
            "rs",
        }

        # Log available dependencies
        self._log_dependencies()

    def _log_dependencies(self):
        """Log which optional dependencies are available"""
        deps = {
            "pandas": PANDAS_AVAILABLE,
            "python-docx": DOCX_AVAILABLE,
            "python-pptx": PPTX_AVAILABLE,
            "Pillow": PILLOW_AVAILABLE,
            "pytesseract": TESSERACT_AVAILABLE,
            "beautifulsoup4": BS4_AVAILABLE,
            "pypdf": PYPDF_AVAILABLE,
        }

        available = [name for name, avail in deps.items() if avail]
        missing = [name for name, avail in deps.items() if not avail]

        self.logger.info(f"Available dependencies: {', '.join(available)}")
        if missing:
            self.logger.warning(f"Missing optional dependencies: {', '.join(missing)}")

    def get_file_extension(self, file_path: str) -> str:
        """Extract file extension from file path"""
        try:
            return os.path.splitext(file_path)[1].lstrip(".").lower()
        except:
            return ""

    def is_supported_file(self, file_path: str) -> bool:
        """Check if file type is supported"""
        extension = self.get_file_extension(file_path)
        return extension in self.supported_extensions

    def process_file(self, file_path: str, custom_meta: Optional[Dict] = None) -> List[LIDoc]:
        """
        Main method to process a file and return llama-index documents

        Args:
            file_path: Path to the file to process
            custom_meta: Optional metadata to add to documents

        Returns:
            List of llama-index Document objects
        """
        if not os.path.exists(file_path):
            self.logger.error(f"File does not exist: {file_path}")
            return []

        extension = self.get_file_extension(file_path)
        self.logger.info(f"Processing {extension} file: {file_path}")

        try:
            # Route to appropriate processor based on file type
            if extension in ["xlsx", "xls"]:
                documents = self._process_excel_file(file_path)
            elif extension == "csv":
                documents = self._process_csv_file(file_path)
            elif extension in ["doc", "docx"]:
                documents = self._process_word_file(file_path)
            elif extension in ["ppt", "pptx"]:
                documents = self._process_powerpoint_file(file_path)
            elif extension in ["json", "jsonl"]:
                documents = self._process_json_file(file_path)
            elif extension in ["png", "jpg", "jpeg", "gif", "bmp", "tiff", "webp"]:
                documents = self._process_image_file(file_path)
            elif extension == "xml":
                documents = self._process_xml_file(file_path)
            elif extension in [
                "txt",
                "md",
                "py",
                "js",
                "html",
                "css",
                "java",
                "cpp",
                "c",
                "php",
                "rb",
                "go",
                "rs",
            ]:
                documents = self._process_text_file(file_path)
            elif extension == "pdf":
                documents = self._process_pdf_file(file_path)
            else:
                # Fallback to SimpleDirectoryReader
                documents = self._process_generic_file(file_path)

            # Add custom metadata to all documents
            if documents and custom_meta:
                for doc in documents:
                    if hasattr(doc, "extra_info") and doc.extra_info is not None:
                        doc.extra_info.update(custom_meta)
                    elif hasattr(doc, "metadata") and doc.metadata is not None:
                        doc.metadata.update(custom_meta)
                    else:
                        # Initialize metadata if it doesn't exist
                        if hasattr(doc, "extra_info"):
                            doc.extra_info = custom_meta.copy()
                        elif hasattr(doc, "metadata"):
                            doc.metadata = custom_meta.copy()

            self.logger.info(
                f"Successfully processed {file_path}: {len(documents)} documents extracted"
            )
            return documents

        except Exception as ex:
            self.logger.error(f"Error processing file {file_path}: {str(ex)}")
            # Try generic processing as fallback
            try:
                return self._process_generic_file(file_path)
            except Exception as fallback_ex:
                self.logger.error(
                    f"Fallback processing also failed for {file_path}: {str(fallback_ex)}"
                )
                return []

    def _process_csv_file(self, file_path: str) -> List[LIDoc]:
        """Process CSV files with enhanced analysis"""
        if not PANDAS_AVAILABLE:
            return self._process_csv_basic(file_path)

        try:
            # Try different encodings
            encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]
            df = None
            used_encoding = None

            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    used_encoding = encoding
                    break
                except (UnicodeDecodeError, pd.errors.EmptyDataError):
                    continue

            if df is None or df.empty:
                self.logger.warning(f"Could not read CSV file or file is empty: {file_path}")
                return []

            # Generate comprehensive text representation
            csv_text = self._generate_csv_analysis(df, file_path, used_encoding)

            # For large datasets, create multiple documents (chunked by rows)
            documents = []
            if len(df) > 1000:
                chunk_size = 500
                for i in range(0, len(df), chunk_size):
                    chunk_df = df.iloc[i : i + chunk_size]
                    chunk_text = f"CSV Data Chunk {i // chunk_size + 1} (rows {i + 1}-{min(i + chunk_size, len(df))}):\n\n"
                    chunk_text += chunk_df.to_string(index=False)
                    documents.append(LIDoc(text=csv_text + "\n\n" + chunk_text))
            else:
                documents.append(LIDoc(text=csv_text))

            return documents

        except Exception as ex:
            self.logger.error(f"Error processing CSV file {file_path}: {str(ex)}")
            return self._process_csv_basic(file_path)

    def _process_csv_basic(self, file_path: str) -> List[LIDoc]:
        """Basic CSV processing without pandas"""
        try:
            import csv

            encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding, newline="") as csvfile:
                        # Detect delimiter
                        sample = csvfile.read(1024)
                        csvfile.seek(0)
                        sniffer = csv.Sniffer()
                        delimiter = sniffer.sniff(sample).delimiter

                        reader = csv.reader(csvfile, delimiter=delimiter)
                        rows = list(reader)

                        if rows:
                            header = rows[0]
                            data_rows = rows[1:] if len(rows) > 1 else []

                            csv_text = f"CSV File Analysis:\n"
                            csv_text += f"File: {os.path.basename(file_path)}\n"
                            csv_text += f"Columns ({len(header)}): {', '.join(header)}\n"
                            csv_text += f"Total rows: {len(data_rows)}\n\n"

                            # Add sample data
                            csv_text += "Sample data (first 10 rows):\n"
                            csv_text += f"{','.join(header)}\n"
                            for row in data_rows[:10]:
                                csv_text += f"{','.join(map(str, row))}\n"

                            return [LIDoc(text=csv_text)]
                    break
                except UnicodeDecodeError:
                    continue

        except Exception as ex:
            self.logger.error(f"Error in basic CSV processing {file_path}: {str(ex)}")
        return []

    def _generate_csv_analysis(self, df, file_path: str, encoding: str) -> str:
        """Generate comprehensive CSV analysis text"""
        analysis = f"CSV File Analysis:\n"
        analysis += f"File: {os.path.basename(file_path)}\n"
        analysis += f"Encoding: {encoding}\n"
        analysis += f"Shape: {df.shape[0]} rows, {df.shape[1]} columns\n"
        analysis += f"Memory usage: {df.memory_usage(deep=True).sum() / 1024:.2f} KB\n\n"

        # Column analysis
        analysis += "Column Analysis:\n"
        for col in df.columns:
            analysis += f"\nColumn '{col}':\n"
            analysis += f"  Data type: {df[col].dtype}\n"
            analysis += f"  Non-null values: {df[col].count()}/{len(df)}\n"
            analysis += f"  Null values: {df[col].isnull().sum()}\n"

            if df[col].dtype in ["object", "string"]:
                unique_count = df[col].nunique()
                analysis += f"  Unique values: {unique_count}\n"
                if unique_count <= 20:
                    unique_vals = df[col].dropna().unique()[:10]
                    analysis += f"  Sample values: {', '.join(map(str, unique_vals))}\n"
            elif pd.api.types.is_numeric_dtype(df[col]):
                analysis += f"  Min: {df[col].min()}\n"
                analysis += f"  Max: {df[col].max()}\n"
                analysis += f"  Mean: {df[col].mean():.2f}\n"

        # Add sample data
        analysis += f"\nSample Data (first 5 rows):\n"
        analysis += df.head().to_string(index=False)

        if len(df) <= 100:
            analysis += f"\n\nComplete Dataset:\n"
            analysis += df.to_string(index=False)

        return analysis

    def _process_json_file(self, file_path: str) -> List[LIDoc]:
        """Process JSON files with structure analysis"""
        try:
            encodings = ["utf-8", "latin-1", "iso-8859-1"]

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        if file_path.endswith(".jsonl"):
                            # Process JSON Lines format
                            return self._process_jsonl_file(f)
                        else:
                            # Process regular JSON
                            data = json.load(f)
                            return self._process_json_data(data, file_path)
                except UnicodeDecodeError:
                    continue

        except Exception as ex:
            self.logger.error(f"Error processing JSON file {file_path}: {str(ex)}")
        return []

    def _process_json_data(self, data: Any, file_path: str) -> List[LIDoc]:
        """Process JSON data structure and convert to searchable documents"""
        try:
            documents = []

            if isinstance(data, list):
                # Handle array of objects (like your sales data)
                if data and isinstance(data[0], dict):
                    # Create summary document
                    summary_text = f"JSON Dataset: {os.path.basename(file_path)}\n\n"
                    summary_text += f"Type: Array of {len(data)} objects\n"

                    # Analyze structure
                    if data:
                        sample_keys = list(data[0].keys())
                        summary_text += f"Object structure: {', '.join(sample_keys)}\n\n"

                        # Create aggregated insights
                        summary_text += "Dataset Insights:\n"
                        summary_text += self._analyze_json_array(data)

                    documents.append(LIDoc(text=summary_text))

                    # Create individual record documents for semantic search
                    for i, item in enumerate(data):
                        record_text = f"Record {i+1} from {os.path.basename(file_path)}:\n"
                        record_text += self._format_json_record(item)

                        # Add metadata for filtering
                        metadata = {
                            "source_file": file_path,
                            "record_index": i,
                            "record_type": "json_object",
                        }

                        doc = LIDoc(text=record_text)
                        if hasattr(doc, "metadata"):
                            doc.metadata = metadata

                        documents.append(doc)

            elif isinstance(data, dict):
                # Single object
                json_text = f"JSON Object: {os.path.basename(file_path)}\n\n"
                json_text += self._format_json_record(data)
                documents.append(LIDoc(text=json_text))

            else:
                # Primitive value
                json_text = f"JSON Value: {os.path.basename(file_path)}\n\n"
                json_text += f"Content: {str(data)}"
                documents.append(LIDoc(text=json_text))

            return documents

        except Exception as ex:
            self.logger.error(f"Error processing JSON data: {str(ex)}")
        return []

    def _analyze_json_array(self, data: List[Dict]) -> str:
        """Analyze array of JSON objects for insights"""
        if not data:
            return "Empty dataset"

        analysis = ""

        # Count unique values for categorical fields
        field_analysis = {}
        for item in data:
            for key, value in item.items():
                if key not in field_analysis:
                    field_analysis[key] = {"values": set(), "types": set()}

                field_analysis[key]["values"].add(str(value))
                field_analysis[key]["types"].add(type(value).__name__)

        # Generate insights
        for field, info in field_analysis.items():
            analysis += f"- {field}: {len(info['values'])} unique values, types: {', '.join(info['types'])}\n"

            # Show sample values for categorical fields
            if len(info["values"]) <= 20:
                sample_values = list(info["values"])[:5]
                analysis += f"  Sample values: {', '.join(sample_values)}\n"

        return analysis

    def _format_json_record(self, record: Dict) -> str:
        """Format a JSON record as searchable text"""
        if not isinstance(record, dict):
            return str(record)

        formatted_parts = []

        for key, value in record.items():
            if isinstance(value, (str, int, float)):
                formatted_parts.append(f"{key}: {value}")
            elif isinstance(value, (list, dict)):
                formatted_parts.append(f"{key}: {json.dumps(value, indent=2)}")
            else:
                formatted_parts.append(f"{key}: {str(value)}")

        return "\n".join(formatted_parts)

    def _process_text_file(self, file_path: str) -> List[LIDoc]:
        """Process plain text files with encoding detection"""
        try:
            encodings = ["utf-8", "latin-1", "iso-8859-1", "cp1252"]

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()

                    if content.strip():
                        # Add file information
                        file_info = f"Text File: {os.path.basename(file_path)}\n"
                        file_info += f"Encoding: {encoding}\n"
                        file_info += f"Length: {len(content)} characters\n"
                        file_info += f"Lines: {content.count(chr(10)) + 1}\n\n"

                        full_content = file_info + content
                        return [LIDoc(text=full_content)]
                    break
                except UnicodeDecodeError:
                    continue

        except Exception as ex:
            self.logger.error(f"Error processing text file {file_path}: {str(ex)}")
        return []

    def _process_pdf_file(self, file_path: str) -> List[LIDoc]:
        """Process PDF files with PyPDF fallback"""
        try:
            # Try SimpleDirectoryReader first
            documents = SimpleDirectoryReader(input_files=[file_path]).load_data()

            # Validate content quality
            valid_docs = []
            for doc in documents:
                if hasattr(doc, "text") and doc.text and self._is_text_readable(doc.text):
                    valid_docs.append(doc)

            if valid_docs:
                return valid_docs
            else:
                raise Exception("No readable content from SimpleDirectoryReader")

        except Exception:
            # Fallback to PyPDF
            if PYPDF_AVAILABLE:
                try:
                    text = self._extract_text_with_pypdf(file_path)
                    if text and self._is_text_readable(text):
                        return [LIDoc(text=text)]
                except Exception as ex:
                    self.logger.error(f"PyPDF extraction failed: {ex}")

        return []

    def _extract_text_with_pypdf(self, pdf_path: str) -> str:
        """Extract text using PyPDF"""
        try:
            text = ""
            with open(pdf_path, "rb") as file:
                pdf_reader = pypdf.PdfReader(file)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text.strip()
        except Exception as e:
            self.logger.error(f"PyPDF extraction failed: {e}")
            return ""

    def _is_text_readable(self, text: str) -> bool:
        """Check if extracted text is readable"""
        if not text:
            return False

        printable_chars = sum(1 for c in text if c.isprintable() or c.isspace())
        total_chars = len(text)

        if total_chars == 0:
            return False

        printable_ratio = printable_chars / total_chars
        return printable_ratio > 0.8

    def _process_generic_file(self, file_path: str) -> List[LIDoc]:
        """Process files using SimpleDirectoryReader as fallback"""
        try:
            return SimpleDirectoryReader(input_files=[file_path]).load_data()
        except Exception as ex:
            self.logger.error(f"Error processing generic file {file_path}: {str(ex)}")
        return []

    # Placeholder methods for other file types
    def _process_excel_file(self, file_path: str) -> List[LIDoc]:
        """Process Excel files - placeholder"""
        return self._process_generic_file(file_path)

    def _process_word_file(self, file_path: str) -> List[LIDoc]:
        """Process Word files - placeholder"""
        return self._process_generic_file(file_path)

    def _process_powerpoint_file(self, file_path: str) -> List[LIDoc]:
        """Process PowerPoint files - placeholder"""
        return self._process_generic_file(file_path)

    def _process_image_file(self, file_path: str) -> List[LIDoc]:
        """Process image files - placeholder"""
        return self._process_generic_file(file_path)

    def _process_xml_file(self, file_path: str) -> List[LIDoc]:
        """Process XML files - placeholder"""
        return self._process_generic_file(file_path)

    def _process_jsonl_file(self, file_handle) -> List[LIDoc]:
        """Process JSON Lines file - placeholder"""
        return []
