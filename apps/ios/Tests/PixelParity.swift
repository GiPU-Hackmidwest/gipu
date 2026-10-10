import Foundation

@main
struct PixelParity {
    static func main() throws {
        guard CommandLine.arguments.count == 3 else { fatalError("usage: pixel-parity INPUT.png OUTPUT.png") }
        let data = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[1]))
        let output = try ImageProcessor.finalize(data, maxPixels: 262144)
        try output.write(to: URL(fileURLWithPath: CommandLine.arguments[2]))
        do {
            _ = try ImageProcessor.finalize(data, maxPixels: 1)
            fatalError("Pixel limit was not enforced")
        } catch ImageProcessor.Failure.tooLarge { }
        print("Swift PNG finishing completed; pixel-limit rejection passed")
    }
}
