"""
PDF Document Generation MCP Server (Stdio JSON-RPC 2.0)
Wraps ReportLab for PDF document creation with B.40 verification.
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

# Ensure UTF-8 I/O on Windows when available
if sys.platform == "win32":
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


def log_debug(msg: str) -> None:
    try:
        sys.stderr.write(f"[MCP PDF Server] {msg}\n")
        sys.stderr.flush()
    except Exception:
        pass


def generate_pdf(file_path: str, title: str, content: str = "", sections: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Generate a formatted PDF document using ReportLab."""
    path = Path(file_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib import colors

        doc = SimpleDocTemplate(
            str(path),
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Title"],
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=14,
        )
        h1_style = ParagraphStyle(
            "DocH1",
            parent=styles["Heading1"],
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=12,
            spaceAfter=6,
        )
        h2_style = ParagraphStyle(
            "DocH2",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#2D3748"),
            spaceBefore=8,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "DocBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#2D3748"),
            spaceAfter=6,
        )
        bullet_style = ParagraphStyle(
            "DocBullet",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            leftIndent=15,
            spaceAfter=4,
        )

        story = []
        # Title
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 10))

        # Explicit sections if provided
        if sections:
            for sec in sections:
                h = sec.get("heading", sec.get("title", ""))
                b = sec.get("body", sec.get("content", ""))
                if h:
                    story.append(Paragraph(h, h1_style))
                if b:
                    for para in b.split("\n\n"):
                        if para.strip():
                            story.append(Paragraph(para.strip().replace("\n", "<br/>"), body_style))
                story.append(Spacer(1, 8))

        # Parse main content markdown if provided
        if content:
            for line in content.split("\n"):
                clean = line.strip()
                if not clean:
                    story.append(Spacer(1, 4))
                elif clean.startswith("### "):
                    story.append(Paragraph(clean[4:], h2_style))
                elif clean.startswith("## "):
                    story.append(Paragraph(clean[3:], h1_style))
                elif clean.startswith("# "):
                    story.append(Paragraph(clean[2:], title_style))
                elif clean.startswith("- ") or clean.startswith("* "):
                    story.append(Paragraph(f"• {clean[2:]}", bullet_style))
                else:
                    # Clean XML characters for reportlab
                    escaped = clean.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    story.append(Paragraph(escaped, body_style))

        doc.build(story)

    except Exception as e:
        log_debug(f"ReportLab PDF generation error: {e}")
        # Fallback minimal plain text PDF generation if reportlab fails
        raise RuntimeError(f"Failed to generate PDF document: {e}")

    # Post-action verification (B.40)
    if not path.exists():
        raise FileNotFoundError(f"Verification Failed: PDF file '{path}' was not written.")

    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise IOError(f"Verification Failed: PDF file '{path}' is 0 bytes.")

    return {
        "file_path": str(path),
        "size_bytes": size_bytes,
        "title": title,
        "status": "success",
        "verified_success": True,
    }


def handle_request(req: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = req.get("method")
    req_id = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "pdf_document_server",
                    "version": "1.0.0",
                },
            },
        }

    elif method == "notifications/initialized":
        return None

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "create_pdf",
                        "description": "Create a formatted, verified PDF document with titles, headings, and styled paragraphs.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Absolute destination path for the generated PDF file",
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Document title heading",
                                },
                                "content": {
                                    "type": "string",
                                    "description": "Complete text or markdown content of the document",
                                },
                                "sections": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "heading": {"type": "string"},
                                            "body": {"type": "string"},
                                        },
                                    },
                                    "description": "Optional list of structured sections with heading and body",
                                },
                            },
                            "required": ["file_path", "title"],
                        },
                    }
                ]
            },
        }

    elif method == "tools/call":
        params = req.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name == "create_pdf":
            file_path = arguments.get("file_path", "")
            title = arguments.get("title", "Document")
            content = arguments.get("content", "")
            sections = arguments.get("sections")

            try:
                res = generate_pdf(file_path, title, content=content, sections=sections)
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(res, indent=2),
                            }
                        ],
                        "isError": False,
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error generating PDF: {e}"}],
                        "isError": True,
                    },
                }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool '{tool_name}'",
                },
            }

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }


def main():
    log_debug("PDF Document MCP Server started over stdio.")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_request(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as e:
            log_debug(f"Error handling request: {e}")
            err_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"},
            }
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
