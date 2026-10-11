import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

enum ImageProcessor {
    enum Failure: Error { case invalidImage, tooLarge, encodingFailed }

    /// V1 runtime finisher. The coordinator verifies exact decoded RGB equality.
    /// Re-encode the decoded image without drawing or color-space conversion.
    static func finalizeInvisible(_ data: Data, maxPixels: Int) throws -> Data {
        try Task.checkCancellation()
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { throw Failure.invalidImage }
        guard image.width >= 8, image.height >= 8, image.width * image.height <= maxPixels else { throw Failure.tooLarge }
        let output = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(output, UTType.png.identifier as CFString, 1, nil) else { throw Failure.encodingFailed }
        CGImageDestinationAddImageFromSource(destination, source, 0, nil)
        try Task.checkCancellation()
        guard CGImageDestinationFinalize(destination) else { throw Failure.encodingFailed }
        return output as Data
    }

    /// Actual local pixel work. Exactly four inner pixels on each edge are teal.
    /// This worker uses one CPU thread; it does not run a diffusion model.
    static func finalize(_ data: Data, maxPixels: Int) throws -> Data {
        try Task.checkCancellation()
        guard let source = CGImageSourceCreateWithData(data as CFData, nil),
              let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else { throw Failure.invalidImage }
        let width = image.width, height = image.height
        guard width >= 8, height >= 8, width * height <= maxPixels else { throw Failure.tooLarge }
        var pixels = [UInt8](repeating: 0, count: width * height * 4)
        try pixels.withUnsafeMutableBytes { buffer in
            guard let context = CGContext(data: buffer.baseAddress, width: width, height: height,
                                          bitsPerComponent: 8, bytesPerRow: width * 4,
                                          space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                          bitmapInfo: CGBitmapInfo.byteOrder32Big.rawValue | CGImageAlphaInfo.premultipliedLast.rawValue) else { throw Failure.invalidImage }
            context.setBlendMode(.copy)
            context.draw(image, in: CGRect(x: 0, y: 0, width: width, height: height))
            let bytes = buffer.bindMemory(to: UInt8.self)
            for y in 0..<height {
                try Task.checkCancellation()
                for x in 0..<width where x < 4 || x >= width - 4 || y < 4 || y >= height - 4 {
                    let index = (y * width + x) * 4
                    bytes[index] = 36; bytes[index + 1] = 203; bytes[index + 2] = 166; bytes[index + 3] = 255
                }
            }
        }
        guard let provider = CGDataProvider(data: Data(pixels) as CFData),
              let framed = CGImage(width: width, height: height, bitsPerComponent: 8, bitsPerPixel: 32,
                                   bytesPerRow: width * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                   bitmapInfo: CGBitmapInfo(rawValue: CGBitmapInfo.byteOrder32Big.rawValue | CGImageAlphaInfo.premultipliedLast.rawValue),
                                   provider: provider, decode: nil, shouldInterpolate: false, intent: .defaultIntent) else { throw Failure.invalidImage }
        let output = NSMutableData()
        guard let destination = CGImageDestinationCreateWithData(output, UTType.png.identifier as CFString, 1, nil) else { throw Failure.encodingFailed }
        CGImageDestinationAddImage(destination, framed, nil)
        guard CGImageDestinationFinalize(destination) else { throw Failure.encodingFailed }
        return output as Data
    }
}
