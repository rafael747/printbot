import functools
import io
import os
import random
import sys
import time
from datetime import datetime
from typing import Any, Literal

import cups
from dotenv import load_dotenv
from escpos.constants import RT_STATUS_ONLINE
from escpos.exceptions import ImageWidthError
from escpos.printer import Network
from fastapi import FastAPI
from pdf2image import convert_from_bytes
from PIL import Image
from pywa import WhatsApp, filters, listeners, types

if sys.platform == "linux":
    import sane  # pylint: disable=import-error
else:
    sane = None


load_dotenv()

PHONE_ID = os.getenv("WA_PHONE_ID")
TOKEN = os.getenv("WA_TOKEN")
VERIFY_TOKEN = os.getenv("WA_VERIFY_TOKEN")
PRINTER_ADDR = os.getenv("PRINTER_ADDR")
PRINTER_PORT = os.getenv("PRINTER_PORT")
PRINTER_SOCKET = os.getenv("PRINTER_SOCKET")
WHITELISTED_NUMBERS = os.getenv("WHITELISTED_NUMBERS").split(",")
CUPS_PRINTER_NAME = os.getenv("CUPS_PRINTER_NAME")


fastapi_app = FastAPI()  # FastAPI server

# Create a WhatsApp client
wa = WhatsApp(
    phone_id=PHONE_ID,
    token=TOKEN,
    server=fastapi_app,  # the server to listen to incoming updates
    webhook_endpoint="/printbot",
    verify_token=VERIFY_TOKEN,  # some random string to verify the webhook
)


def get_random_emoji() -> str:
    """Get a random emoji from a predefined list"""
    # fmt: off
    return random.choice(
        ["👍", "🤘", "👌", "🫡", "🥸", "❤", "👋", "🙏", "💪", "👏", "🤝", "🤛", "🤜", "🤞"],
    )
    # fmt: on


def check_user(func):
    """Check if the user is whitelisted to use the bot (if number is in WHITELISTED_NUMBERS)."""

    @functools.wraps(func)
    def wrapper(client: WhatsApp, msg: types.Message):
        if msg.from_user.wa_id not in WHITELISTED_NUMBERS:
            msg.react("🚫")
            msg.reply_text(
                "You are not whitelisted to use this bot. Please contact the admin to be whitelisted."
            )
            return False
        msg.react(get_random_emoji())
        return func(client, msg)

    return wrapper


def _report_job(
    job: types.Message | None, success: bool, error_message: str | None = None
) -> None:
    """React to the user's job message and optionally send an error message."""
    if not job:
        return
    job.react("✅" if success else "❌")
    if not success and error_message:
        job.reply_text(error_message)


def send_to_printer(
    data: Any,
    data_type: Literal["text", "image", "qr", "control"],
    job: types.Message | None = None,
    caption: str | None = None,
) -> bool:
    """Send content to the network printer and optionally report status to the user."""
    printer = None
    try:
        printer = Network(
            host=PRINTER_ADDR,
            port=int(PRINTER_PORT),
            profile="ZJ-5870",
            timeout=10,
        )

        if data_type == "text":
            printer.text(data)
        elif data_type == "image":
            target_width = printer.profile.profile_data["media"]["width"]["pixels"]
            if data.width > target_width:
                ratio = target_width / data.width
                new_height = int(data.height * ratio)
                data = data.resize((target_width, new_height), Image.Resampling.LANCZOS)
            printer.image(center=True, img_source=data)
            time.sleep(5)  # for slow prints
        elif data_type == "qr":
            printer.qr(content=data, size=9, center=True)
        elif data_type == "control":
            if data == RT_STATUS_ONLINE:
                return printer.is_online()
            return False

        if caption:
            printer.set(align="center")
            printer.block_text(caption)
            printer.set_with_default()
        printer.ln(3)
        status = printer.is_online()
        _report_job(job, status)
        return status

    except ImageWidthError:
        _report_job(job, False, "Ops, the image is too wide to print.")
        return False
    except Exception as e:
        print(f"Error sending to printer: {e}")
        _report_job(job, False)
        return False
    finally:
        if printer:
            try:
                printer.close()
            except Exception as e:
                print(f"Error closing printer: {e}")


# Handle incoming messages
@wa.on_message(
    filters.matches("Hey", "Hi", "Help", "Hello", "Config", ignore_case=True),
    priority=10,
)
@check_user
def help_menu(client: WhatsApp, msg: types.Message):
    """Show the help menu to the user."""
    msg.react("🚧")
    msg.reply_text(
        text=f"Hello {msg.from_user.name}! How can I help you today?",
        buttons=[
            types.Button(title="Scan document", callback_data="scan_document"),
            types.Button(title="Check printer", callback_data="check_printer_status"),
            types.Button(
                title="Whitelist number", callback_data="whitelist_phone_number"
            ),
        ],
    )


@wa.on_message(filters.text, priority=5)  # Filter to match text messages
@check_user
def print_text(client: WhatsApp, msg: types.Message):
    """Print text messages in the thermal printer."""
    option = msg.reply_text(
        text="Text received, do you want to print it?",
        buttons=[
            types.Button(title="Print", callback_data="print_text"),
            types.Button(title="Print as QR code", callback_data="print_qr_code"),
            types.Button(title="Cancel", callback_data="cancel_print_text"),
        ],
        quote=True,
    )
    try:
        click = option.wait_for_click(timeout=60)
    except listeners.ListenerTimeout:
        msg.reply_text("Timeout waiting for option")  # Reply to the button click
        return
    if click.data == "print_text":
        job = msg.reply_text("Printing text...")  # Reply to the button click
        send_to_printer(msg.text, "text", job)
    if click.data == "print_qr_code":
        job = msg.reply_text("Printing QR code...")  # Reply to the button click
        send_to_printer(msg.text, "qr", job)
    return


@wa.on_message(filters.image)  # Filter to match image messages
@check_user
def print_image(client: WhatsApp, msg: types.Message):
    """Print images in the thermal printer."""
    option = msg.reply_text(
        text="Image received, do you want to print it?",
        buttons=[
            types.Button(title="Print", callback_data="print_image"),
            types.Button(title="Cancel", callback_data="cancel_print_image"),
        ],
        quote=True,
    )
    try:
        click = option.wait_for_click(timeout=60)
    except listeners.ListenerTimeout:
        msg.reply_text("Timeout waiting for option")  # Reply to the button click
        return
    if click.data == "print_image":
        job = msg.reply_text("Printing image...")  # Reply to the button click
        image_to_print = Image.open(io.BytesIO(msg.media.get_bytes()))
        send_to_printer(image_to_print, "image", job, msg.caption)
    return


@wa.on_message(filters.document)
@check_user
def print_document(client: WhatsApp, msg: types.Message):
    """Print PDF documents on the thermal printer or the normal printer."""
    if msg.document.extension != ".pdf":
        _report_job(msg, False, "Only PDF documents are supported.")
        return
    option = msg.reply_text(
        text="Document received, do you want to print it?",
        buttons=[
            types.Button(title="Normal printer", callback_data="print_on_printer"),
            types.Button(title="Thermal printer", callback_data="print_on_thermal"),
            types.Button(title="Cancel", callback_data="cancel_print"),
        ],
        quote=True,
    )
    try:
        click = option.wait_for_click(timeout=60)
    except listeners.ListenerTimeout:
        msg.reply_text("Timeout waiting for option")  # Reply to the button click
        return
    if click.data == "print_on_thermal":
        job = msg.reply_text(
            "Printing document on thermal printer..."
        )  # Reply to the button click
        pages = convert_from_bytes(
            pdf_file=msg.document.get_bytes(), dpi=200, grayscale=True
        )
        for page in pages:
            send_to_printer(page, "image", job)
    if click.data == "print_on_printer":
        job = msg.reply_text(
            "Printing document on normal printer..."
        )  # Reply to the button click
        try:
            document = msg.document.download(path="/tmp")
            # print on cups printer
            c = cups.Connection()
            c.printFile(
                CUPS_PRINTER_NAME,
                str(document),
                f"printbot - {msg.document.filename}",
                {},
            )
            document.unlink()
            job.react("✅")
        except Exception as e:
            print(e)
            job.react("❌")


# Handle incoming button clicks
@wa.on_callback_button(filters.matches("scan_document"))
def scan_document(client: WhatsApp, clb: types.CallbackButton):
    """Scan documents on the normal printer's scanner."""
    option = clb.reply_text(
        text="How do you want to scan it?",
        buttons=[
            types.Button(title="Color Scan, Low Res", callback_data="color_scan_low"),
            types.Button(title="Color Scan, High Res", callback_data="color_scan_high"),
            types.Button(title="BW Scan, Low Res", callback_data="bw_scan_low"),
            #  types.Button(
            #      title="BW Scan, High Resolution",
            #      callback_data="bw_scan_high"
            #  ),
        ],
        quote=True,
    )
    try:
        click = option.wait_for_click(timeout=60)
    except listeners.ListenerTimeout:
        clb.reply_text("Timeout waiting for option")
        return
    # define mode and resolution
    mode = "color"
    resolution = 75
    if click.data == "color_scan_high":
        mode = "color"
        resolution = 300
    if click.data == "bw_scan_low":
        mode = "gray"
        resolution = 75
    if click.data == "bw_scan_high":
        mode = "gray"
        resolution = 300

    click.react("🔄")

    if sane is None:
        _report_job(click, False, "Scanning is only available on Linux.")
        return
    sane.init()
    dev = sane.open(sane.get_devices()[0][0])
    dev.mode = mode
    dev.resolution = resolution
    dev.br_y = 297
    dev.br_x = 210
    doc = dev.scan()
    dev.close()
    if doc.mode != "RGB":
        doc = doc.convert("RGB")

    doc_buffer = io.BytesIO()
    doc.save(doc_buffer, format="PDF")
    click.react("✅")
    clb.reply_document(
        document=doc_buffer,
        filename=datetime.now().strftime("%Y.%m.%d_%H.%M.%S.pdf"),
    )
    doc_buffer.close()


@wa.on_callback_button(filters.matches("check_printer_status"))
def check_printer_status(client: WhatsApp, clb: types.CallbackButton):
    """Check the status of both the thermal printer and the normal printer."""
    if send_to_printer(RT_STATUS_ONLINE, "control", None):
        clb.reply_text("Thermal printer status: OK")
    else:
        clb.reply_text("Thermal printer status: Not Connected")
    c = cups.Connection()
    status = c.getPrinters()[CUPS_PRINTER_NAME]["printer-state"]
    status_map = {3: "OK (Idle)", 4: "Printing", 5: "Stopped"}
    clb.reply_text(f"Epson printer status: {status_map[status]}")


@wa.on_callback_button(filters.matches("whitelist_phone_number"))
def whitelist_phone_number(client: WhatsApp, clb: types.CallbackButton):
    """Whitelist phone numbers to use the bot."""
    try:
        msg = clb.reply_text("Send me the contact to be whitelisted").wait_for_reply(
            filters=filters.contacts, timeout=60
        )
        contact_number = msg.contacts[0].phones[0].phone
        contact_wa_id = msg.contacts[0].phones[0].wa_id
        contact_name = msg.contacts[0].name.formatted_name
        if contact_wa_id:
            clb.reply_text(
                f"Whitelisting phone number {contact_number} from {contact_name}"
            )
        else:
            clb.reply_text(
                f"Phone number {contact_number} from {contact_name} is not a valid WhatsApp number."
            )
        WHITELISTED_NUMBERS.append(contact_wa_id)
    except listeners.ListenerTimeout:
        clb.reply_text("Timeout waiting for contact")
        return
