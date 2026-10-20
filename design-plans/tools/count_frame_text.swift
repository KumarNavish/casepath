// Count rendered text regions in a frame with the same offline OCR settings.
// swift count_frame_text.swift <image.png> > <receipt.json>
import Foundation
import Vision
import ImageIO
let input = CommandLine.arguments[1]
let url = URL(fileURLWithPath: input)
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = false
request.recognitionLanguages = ["en-US"]
try VNImageRequestHandler(url: url).perform([request])
let rows: [[String: Any]] = (request.results ?? []).compactMap { row in
    guard let text = row.topCandidates(1).first else { return nil }
    let b = row.boundingBox
    return ["text": text.string, "confidence": text.confidence, "box": [b.minX, b.minY, b.width, b.height]]
}
let result: [String: Any] = ["image": input, "method": "Apple Vision accurate OCR, en-US, no language correction; one detected text region is one visible text element", "count": rows.count, "regions": rows]
let data = try JSONSerialization.data(withJSONObject: result, options: [.prettyPrinted, .sortedKeys])
print(String(data: data, encoding: .utf8)!)
