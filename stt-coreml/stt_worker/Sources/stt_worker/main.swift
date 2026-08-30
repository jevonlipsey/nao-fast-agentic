import Foundation
import FluidAudio

@main
struct STTWorker {
    static func main() async throws {
        // Initialize the transcriber and load the Neural Engine model into RAM
        // We explicitly use pktv3 (Parakeet TDT v3)
        let tdtModels = try await AsrModels.downloadAndLoad(version: .v3)
        let manager = AsrManager(config: .default)
        
        try await manager.loadModels(tdtModels)
        
        let converter = AudioConverter()

        fputs("[[STT_WORKER]]: ready\n", stderr)
        
        // Loop continuously, waiting for Python to pipe a file path
        while let filePath = readLine() {
            let path = filePath.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !path.isEmpty else { continue }
            
            let url = URL(fileURLWithPath: path)
            guard FileManager.default.fileExists(atPath: url.path) else {
                fputs("Error: File not found \(path)\n", stderr)
                continue
            }
            
            do {
                // 1. Load and resample audio using FluidAudio's helper
                let samples = try converter.resampleAudioFile(url)
                
                // 2. Setup the decoder state required for pktv3
                var decoderState = TdtDecoderState.make(decoderLayers: await manager.decoderLayerCount)
                
                // 3. Transcribe instantly using the pre-loaded CoreML model
                let result = try await manager.transcribe(samples, decoderState: &decoderState)
                
                // 4. Print ONLY the transcription to stdout for Python to capture
                print(result.text)
                fflush(stdout)
                
            } catch {
                fputs("Transcription failed: \(error)\n", stderr)
                // Print a blank line so Python knows we finished processing but failed
                print("")
                fflush(stdout)
            }
        }
    }
}
