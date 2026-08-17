import AVFoundation
import CoreMedia
import CoreVideo
import Foundation

private let headerMagic = Data([0x48, 0x52, 0x43, 0x31]) // "HRC1"

private func stderr(_ message: String) {
    FileHandle.standardError.write(Data((message + "\n").utf8))
}

private func littleEndianData<T: FixedWidthInteger>(_ value: T) -> Data {
    var encoded = value.littleEndian
    return Data(bytes: &encoded, count: MemoryLayout<T>.size)
}

private final class FrameWriter: NSObject, AVCaptureVideoDataOutputSampleBufferDelegate {
    private let outputHandle = FileHandle.standardOutput
    private let expectedWidth: Int
    private let expectedHeight: Int

    init(expectedWidth: Int, expectedHeight: Int) {
        self.expectedWidth = expectedWidth
        self.expectedHeight = expectedHeight
    }

    func captureOutput(
        _ captureOutput: AVCaptureOutput,
        didOutput sampleBuffer: CMSampleBuffer,
        from connection: AVCaptureConnection
    ) {
        guard let pixelBuffer = CMSampleBufferGetImageBuffer(sampleBuffer) else { return }
        CVPixelBufferLockBaseAddress(pixelBuffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pixelBuffer, .readOnly) }

        guard let base = CVPixelBufferGetBaseAddress(pixelBuffer) else { return }
        let width = CVPixelBufferGetWidth(pixelBuffer)
        let height = CVPixelBufferGetHeight(pixelBuffer)
        guard width == expectedWidth && height == expectedHeight else {
            stderr(
                "AVFoundation returned \(width)x\(height), expected "
                    + "\(expectedWidth)x\(expectedHeight)."
            )
            exit(65)
        }
        let bytesPerRow = CVPixelBufferGetBytesPerRow(pixelBuffer)
        let payloadBytes = bytesPerRow * height

        var header = headerMagic
        header.append(littleEndianData(UInt32(width)))
        header.append(littleEndianData(UInt32(height)))
        header.append(littleEndianData(UInt32(bytesPerRow)))
        header.append(littleEndianData(UInt32(payloadBytes)))
        header.append(littleEndianData(DispatchTime.now().uptimeNanoseconds))
        outputHandle.write(header)
        outputHandle.write(Data(bytes: base, count: payloadBytes))
    }
}

private func integerArgument(_ index: Int, name: String) -> Int32 {
    guard CommandLine.arguments.count > index,
          let value = Int32(CommandLine.arguments[index]), value > 0 else {
        stderr("Expected positive integer argument: \(name)")
        exit(64)
    }
    return value
}

guard CommandLine.arguments.count == 5 else {
    stderr("Usage: avfoundation-uid-capture <unique-id> <width> <height> <fps>")
    exit(64)
}

let uniqueID = CommandLine.arguments[1]
let requestedWidth = integerArgument(2, name: "width")
let requestedHeight = integerArgument(3, name: "height")
let requestedFPS = integerArgument(4, name: "fps")

guard let device = AVCaptureDevice(uniqueID: uniqueID) else {
    stderr("No AVFoundation camera has uniqueID '\(uniqueID)'.")
    exit(66)
}

let session = AVCaptureSession()
session.beginConfiguration()
let requestedPreset: AVCaptureSession.Preset? = switch (requestedWidth, requestedHeight) {
case (640, 480): .vga640x480
case (1280, 720): .hd1280x720
case (1920, 1080): .hd1920x1080
default: nil
}

do {
    let input = try AVCaptureDeviceInput(device: device)
    guard session.canAddInput(input) else {
        stderr("AVFoundation refused the camera input '\(uniqueID)'.")
        exit(69)
    }
    session.addInput(input)
    // canSetSessionPreset is only authoritative after an input belongs to the
    // session. Asked before addInput it returned false and silently left these
    // webcams at 1920x1080.
    if let preset = requestedPreset, session.canSetSessionPreset(preset) {
        session.sessionPreset = preset
    }
} catch {
    stderr("Could not open AVFoundation camera '\(uniqueID)': \(error)")
    exit(69)
}

let output = AVCaptureVideoDataOutput()
output.alwaysDiscardsLateVideoFrames = true
output.videoSettings = [
    kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
    kCVPixelBufferWidthKey as String: requestedWidth,
    kCVPixelBufferHeightKey as String: requestedHeight,
]
private let writer = FrameWriter(
    expectedWidth: Int(requestedWidth),
    expectedHeight: Int(requestedHeight)
)
let captureQueue = DispatchQueue(label: "tr.hashtagrobotics.avfoundation.\(uniqueID)")
output.setSampleBufferDelegate(writer, queue: captureQueue)
guard session.canAddOutput(output) else {
    stderr("AVFoundation refused the video output for '\(uniqueID)'.")
    exit(69)
}
session.addOutput(output)
session.commitConfiguration()

do {
    try device.lockForConfiguration()
    defer { device.unlockForConfiguration() }

    let matchingFormats = device.formats.filter { format in
        let dimensions = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
        guard dimensions.width == requestedWidth && dimensions.height == requestedHeight else {
            return false
        }
        return format.videoSupportedFrameRateRanges.contains { range in
            // The camera calls its NTSC-derived 29.99997 rate "30". A strict
            // floating-point comparison rejects the correct 640x480 format and
            // leaves AVFoundation at its 1920x1080 default.
            range.minFrameRate <= Double(requestedFPS) + 0.1
                && range.maxFrameRate >= Double(requestedFPS) - 0.1
        }
    }
    guard let format = matchingFormats.first else {
        stderr(
            "Camera '\(uniqueID)' does not support "
                + "\(requestedWidth)x\(requestedHeight) at \(requestedFPS) FPS."
        )
        exit(65)
    }
    device.activeFormat = format
    // UVC cameras often advertise 29.97-ish timing as
    // 1_000_000/30_000_030 rather than the mathematically exact 1/30. Passing
    // an invented CMTime raises an Objective-C exception, so use the duration
    // the active format itself publishes for the nearest supported rate.
    if let frameRate = device.activeFormat.videoSupportedFrameRateRanges.min(by: {
        abs($0.maxFrameRate - Double(requestedFPS))
            < abs($1.maxFrameRate - Double(requestedFPS))
    }) {
        device.activeVideoMinFrameDuration = frameRate.minFrameDuration
        device.activeVideoMaxFrameDuration = frameRate.minFrameDuration
    }
    let activeDimensions = CMVideoFormatDescriptionGetDimensions(
        device.activeFormat.formatDescription
    )
    stderr(
        "CONFIG\t\(uniqueID)\t\(activeDimensions.width)x\(activeDimensions.height)"
            + "\t\(device.activeVideoMinFrameDuration.value)/"
            + "\(device.activeVideoMinFrameDuration.timescale)"
    )
} catch {
    stderr("Could not configure AVFoundation camera '\(uniqueID)': \(error)")
    exit(69)
}

session.startRunning()
guard session.isRunning else {
    stderr("AVFoundation camera '\(uniqueID)' did not start.")
    exit(69)
}

stderr("READY\t\(uniqueID)\t\(requestedWidth)x\(requestedHeight)\t\(requestedFPS)")
RunLoop.current.run()
