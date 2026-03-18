#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "demo" / "troubleshooting-strong-feedback.gif"


SCENES = [
    {
        "duration": 0.9,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
        ],
    },
    {
        "duration": 0.6,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
        ],
    },
    {
        "duration": 0.6,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
            {"text": "assistant> 识别目标/范围", "kind": "progress"},
        ],
    },
    {
        "duration": 0.7,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
            {"text": "assistant> 识别目标/范围", "kind": "progress"},
            {"text": "assistant> 生成调查计划", "kind": "progress"},
        ],
    },
    {
        "duration": 1.4,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
            {"text": "assistant> 识别目标/范围", "kind": "progress"},
            {"text": "assistant> 生成调查计划", "kind": "progress"},
            {
                "text": "assistant> 为了先确认最近的异常线索，所以先读取日志，判断问题更像报错、超时还是依赖异常。",
                "kind": "reason",
            },
        ],
    },
    {
        "duration": 1.0,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
            {"text": "assistant> 识别目标/范围", "kind": "progress"},
            {"text": "assistant> 生成调查计划", "kind": "progress"},
            {
                "text": "assistant> 为了先确认最近的异常线索，所以先读取日志，判断问题更像报错、超时还是依赖异常。",
                "kind": "reason",
            },
            {
                "text": "assistant> 正在读取日志：read_log_tail(/var/log/app.log)",
                "kind": "action",
            },
        ],
    },
    {
        "duration": 0.9,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
            {"text": "assistant> 识别目标/范围", "kind": "progress"},
            {"text": "assistant> 生成调查计划", "kind": "progress"},
            {
                "text": "assistant> 为了先确认最近的异常线索，所以先读取日志，判断问题更像报错、超时还是依赖异常。",
                "kind": "reason",
            },
            {
                "text": "assistant> 正在读取日志：read_log_tail(/var/log/app.log)",
                "kind": "action",
            },
            {"text": "assistant> 仍在读取日志，请稍等。", "kind": "heartbeat"},
        ],
    },
    {
        "duration": 0.5,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
            {"text": "assistant> 识别目标/范围", "kind": "progress"},
            {"text": "assistant> 生成调查计划", "kind": "progress"},
            {
                "text": "assistant> 为了先确认最近的异常线索，所以先读取日志，判断问题更像报错、超时还是依赖异常。",
                "kind": "reason",
            },
            {
                "text": "assistant> 正在读取日志：read_log_tail(/var/log/app.log)",
                "kind": "action",
            },
            {"text": "assistant> 仍在读取日志，请稍等。", "kind": "heartbeat"},
            {"text": "assistant> 汇总证据", "kind": "progress"},
        ],
    },
    {
        "duration": 0.8,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
            {"text": "assistant> 识别目标/范围", "kind": "progress"},
            {"text": "assistant> 生成调查计划", "kind": "progress"},
            {
                "text": "assistant> 为了先确认最近的异常线索，所以先读取日志，判断问题更像报错、超时还是依赖异常。",
                "kind": "reason",
            },
            {
                "text": "assistant> 正在读取日志：read_log_tail(/var/log/app.log)",
                "kind": "action",
            },
            {"text": "assistant> 仍在读取日志，请稍等。", "kind": "heartbeat"},
            {"text": "assistant> 汇总证据", "kind": "progress"},
            {"text": "assistant> 刚才先检查了日志；下面给出当前判断。", "kind": "summary"},
        ],
    },
    {
        "duration": 0.8,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
            {"text": "assistant> 识别目标/范围", "kind": "progress"},
            {"text": "assistant> 生成调查计划", "kind": "progress"},
            {
                "text": "assistant> 为了先确认最近的异常线索，所以先读取日志，判断问题更像报错、超时还是依赖异常。",
                "kind": "reason",
            },
            {
                "text": "assistant> 正在读取日志：read_log_tail(/var/log/app.log)",
                "kind": "action",
            },
            {"text": "assistant> 仍在读取日志，请稍等。", "kind": "heartbeat"},
            {"text": "assistant> 汇总证据", "kind": "progress"},
            {"text": "assistant> 刚才先检查了日志；下面给出当前判断。", "kind": "summary"},
            {"text": "assistant> 输出判断", "kind": "progress"},
        ],
    },
    {
        "duration": 1.8,
        "lines": [
            {"text": "ruibin@hciguard % nanobot agent", "kind": "prompt"},
            {"text": "", "kind": "muted"},
            {
                "text": "user> 检查 /var/log/app.log 最近 200 行是否有 timeout，并给出结论",
                "kind": "user",
            },
            {"text": "assistant> 初始化上下文", "kind": "progress"},
            {"text": "assistant> 识别目标/范围", "kind": "progress"},
            {"text": "assistant> 生成调查计划", "kind": "progress"},
            {
                "text": "assistant> 为了先确认最近的异常线索，所以先读取日志，判断问题更像报错、超时还是依赖异常。",
                "kind": "reason",
            },
            {
                "text": "assistant> 正在读取日志：read_log_tail(/var/log/app.log)",
                "kind": "action",
            },
            {"text": "assistant> 仍在读取日志，请稍等。", "kind": "heartbeat"},
            {"text": "assistant> 汇总证据", "kind": "progress"},
            {"text": "assistant> 刚才先检查了日志；下面给出当前判断。", "kind": "summary"},
            {"text": "assistant> 输出判断", "kind": "progress"},
            {
                "text": "assistant> 结论：最近日志里能看到 timeout，当前更像请求超时或下游依赖响应慢，暂未看到服务退出迹象。",
                "kind": "final",
            },
        ],
    },
]


SWIFT_SOURCE = r"""
import AppKit
import Foundation

struct SceneLine: Decodable {
    let text: String
    let kind: String
}

struct Scene: Decodable {
    let duration: Double
    let lines: [SceneLine]
}

let metadataPath = CommandLine.arguments[1]
let outputDir = CommandLine.arguments[2]
let data = try Data(contentsOf: URL(fileURLWithPath: metadataPath))
let scenes = try JSONDecoder().decode([Scene].self, from: data)

let width: CGFloat = 1400
let height: CGFloat = 920
let windowInset: CGFloat = 42
let contentInsetX: CGFloat = 72
let contentInsetTop: CGFloat = 92
let maxTextWidth: CGFloat = width - contentInsetX * 2 - windowInset * 2

func color(_ hex: UInt32, alpha: CGFloat = 1.0) -> NSColor {
    return NSColor(
        calibratedRed: CGFloat((hex >> 16) & 0xff) / 255.0,
        green: CGFloat((hex >> 8) & 0xff) / 255.0,
        blue: CGFloat(hex & 0xff) / 255.0,
        alpha: alpha
    )
}

func attrs(for kind: String) -> [NSAttributedString.Key: Any] {
    let font = NSFont.systemFont(ofSize: 29, weight: kind == "final" ? .medium : .regular)
    let paragraph = NSMutableParagraphStyle()
    paragraph.lineSpacing = 6
    let foreground: NSColor
    switch kind {
    case "prompt":
        foreground = color(0x7ee787)
    case "user":
        foreground = color(0xa5d6ff)
    case "progress":
        foreground = color(0xf0f6fc)
    case "reason":
        foreground = color(0xffd866)
    case "action":
        foreground = color(0x79c0ff)
    case "heartbeat":
        foreground = color(0xffa657)
    case "summary":
        foreground = color(0xd2a8ff)
    case "final":
        foreground = color(0xffffff)
    default:
        foreground = color(0x8b949e)
    }
    return [
        .font: font,
        .foregroundColor: foreground,
        .paragraphStyle: paragraph,
    ]
}

func lineHeight(for text: String, kind: String) -> CGFloat {
    let attributed = NSAttributedString(string: text, attributes: attrs(for: kind))
    let rect = attributed.boundingRect(
        with: NSSize(width: maxTextWidth, height: 2000),
        options: [.usesLineFragmentOrigin, .usesFontLeading]
    )
    return ceil(rect.height)
}

func drawScene(_ scene: Scene, index: Int) throws {
    let image = NSImage(size: NSSize(width: width, height: height))
    image.lockFocus()

    color(0x0b1016).setFill()
    NSBezierPath(rect: NSRect(x: 0, y: 0, width: width, height: height)).fill()

    let shadow = NSShadow()
    shadow.shadowBlurRadius = 18
    shadow.shadowOffset = NSSize(width: 0, height: -6)
    shadow.shadowColor = color(0x000000, alpha: 0.25)
    shadow.set()

    let windowRect = NSRect(
        x: windowInset,
        y: windowInset,
        width: width - windowInset * 2,
        height: height - windowInset * 2
    )
    let terminal = NSBezierPath(roundedRect: windowRect, xRadius: 18, yRadius: 18)
    color(0x0d1117).setFill()
    terminal.fill()

    let titleBar = NSBezierPath(
        roundedRect: NSRect(x: windowRect.minX, y: windowRect.maxY - 52, width: windowRect.width, height: 52),
        xRadius: 18,
        yRadius: 18
    )
    color(0x161b22).setFill()
    titleBar.fill()
    NSBezierPath(rect: NSRect(x: windowRect.minX, y: windowRect.maxY - 52, width: windowRect.width, height: 26)).fill()

    let trafficY = windowRect.maxY - 31
    for (offset, hex) in [(78.0, 0xff5f57), (102.0, 0xfebc2e), (126.0, 0x28c840)] {
        let dot = NSBezierPath(ovalIn: NSRect(x: offset, y: trafficY, width: 14, height: 14))
        color(UInt32(hex)).setFill()
        dot.fill()
    }

    let titleAttrs: [NSAttributedString.Key: Any] = [
        .font: NSFont.systemFont(ofSize: 17, weight: .medium),
        .foregroundColor: color(0x8b949e),
    ]
    let title = "HCIGuard Troubleshooting Demo"
    title.draw(at: NSPoint(x: width / 2 - 132, y: windowRect.maxY - 35), withAttributes: titleAttrs)

    let divider = NSBezierPath(rect: NSRect(x: windowRect.minX, y: windowRect.maxY - 52, width: windowRect.width, height: 1))
    color(0x21262d).setFill()
    divider.fill()

    var currentTop = windowRect.maxY - contentInsetTop
    for line in scene.lines {
        if line.text.isEmpty {
            currentTop -= 14
            continue
        }
        let attributed = NSAttributedString(string: line.text, attributes: attrs(for: line.kind))
        let heightNeeded = lineHeight(for: line.text, kind: line.kind)
        let drawRect = NSRect(
            x: windowRect.minX + contentInsetX,
            y: currentTop - heightNeeded,
            width: maxTextWidth,
            height: heightNeeded
        )
        attributed.draw(with: drawRect, options: [.usesLineFragmentOrigin, .usesFontLeading])
        currentTop -= heightNeeded + 10
    }

    image.unlockFocus()

    let tiff = image.tiffRepresentation!
    let rep = NSBitmapImageRep(data: tiff)!
    let png = rep.representation(using: .png, properties: [:])!
    let output = URL(fileURLWithPath: outputDir).appendingPathComponent(String(format: "frame-%02d.png", index))
    try png.write(to: output)
}

for (index, scene) in scenes.enumerated() {
    try drawScene(scene, index: index)
}
"""


def run(cmd: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def render_frames(tmpdir: Path) -> list[Path]:
    metadata_path = tmpdir / "scenes.json"
    metadata_path.write_text(json.dumps(SCENES, ensure_ascii=False, indent=2), encoding="utf-8")
    swift_path = tmpdir / "render.swift"
    swift_path.write_text(SWIFT_SOURCE, encoding="utf-8")
    frames_dir = tmpdir / "frames"
    frames_dir.mkdir()
    run(["swift", str(swift_path), str(metadata_path), str(frames_dir)])
    return sorted(frames_dir.glob("frame-*.png"))


def render_gif(frames: list[Path], tmpdir: Path) -> None:
    concat_path = tmpdir / "frames.txt"
    lines: list[str] = []
    for frame, scene in zip(frames, SCENES, strict=True):
        lines.append(f"file '{frame.as_posix()}'")
        lines.append(f"duration {scene['duration']}")
    lines.append(f"file '{frames[-1].as_posix()}'")
    concat_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    palette_path = tmpdir / "palette.png"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-vf",
            "fps=12,scale=1200:-1:flags=lanczos,palettegen",
            str(palette_path),
        ]
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-i",
            str(palette_path),
            "-lavfi",
            "fps=12,scale=1200:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
            "-loop",
            "0",
            str(OUTPUT),
        ]
    )


def main() -> None:
    if shutil.which("swift") is None:
        raise SystemExit("swift not found")
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        frames = render_frames(tmpdir)
        if not frames:
            raise SystemExit("no frames rendered")
        render_gif(frames, tmpdir)
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
