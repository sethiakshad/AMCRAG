import Foundation
import Vision
import AppKit

struct PageResult: Codable {
    let page: Int
    let text: String
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    fputs("Usage: fast_ocr <images_dir> <start_page> <end_page>\n", stderr)
    exit(1)
}

let imagesDir = args[1]
let startPage = Int(args[2]) ?? 1
let endPage = Int(args[3]) ?? startPage

var results: [PageResult] = []

for pageNum in startPage...endPage {
    let padded = String(format: "%03d", pageNum)
    let path = "\(imagesDir)/page_\(padded).png"
    guard FileManager.default.fileExists(atPath: path) else { continue }
    
    guard let image = NSImage(contentsOfFile: path),
          let tiffData = image.tiffRepresentation,
          let bitmap = NSBitmapImageRep(data: tiffData),
          let cgImage = bitmap.cgImage else {
        continue
    }
    
    var pageLines: [String] = []
    let request = VNRecognizeTextRequest { (request, error) in
        guard let observations = request.results as? [VNRecognizedTextObservation] else { return }
        for observation in observations {
            if let top = observation.topCandidates(1).first {
                pageLines.append(top.string)
            }
        }
    }
    request.recognitionLevel = .accurate
    let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
    try? handler.perform([request])
    
    let joined = pageLines.joined(separator: "\n")
    results.append(PageResult(page: pageNum, text: joined))
    fputs("Processed page \(pageNum) (\(pageLines.count) lines)\n", stderr)
}

let encoder = JSONEncoder()
encoder.outputFormatting = .prettyPrinted
if let data = try? encoder.encode(results), let jsonStr = String(data: data, encoding: .utf8) {
    print(jsonStr)
}
