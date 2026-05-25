import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/voice/tts
 *
 * Proxies a TTS synthesis request to the internal FastAPI ML service
 * (/tts/generate). Keeping the ML_SERVICE_URL server-side ensures:
 *  - No CORS issues from the browser.
 *  - The internal service URL is never exposed to clients.
 *
 * Request body: { text: string; language_code: string }
 * Response:     audio/mpeg stream  (or JSON error)
 */
export async function POST(req: NextRequest) {
    try {
        const body = await req.json();
        const { text, language_code } = body as { text?: string; language_code?: string };

        if (!text?.trim()) {
            return NextResponse.json({ error: "text is required" }, { status: 400 });
        }

        const mlServiceUrl = process.env.ML_SERVICE_URL ?? "http://localhost:8000";
        const targetUrl = `${mlServiceUrl}/tts/generate`;

        const mlResponse = await fetch(targetUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: text.trim(),
                language_code: language_code ?? "en-IN",
            }),
            // 15-second hard timeout — Polly is fast but network can vary
            signal: AbortSignal.timeout(15_000),
        });

        if (!mlResponse.ok) {
            let detail = `ML TTS service returned HTTP ${mlResponse.status}`;
            try {
                const err = (await mlResponse.json()) as { detail?: string };
                if (err.detail) detail = err.detail;
            } catch {
                // non-JSON body – keep generic message
            }
            return NextResponse.json({ error: detail }, { status: mlResponse.status });
        }

        // Stream the audio bytes straight back to the browser
        const audioBuffer = await mlResponse.arrayBuffer();

        return new NextResponse(audioBuffer, {
            status: 200,
            headers: {
                "Content-Type": "audio/mpeg",
                "Cache-Control": "no-store",
            },
        });
    } catch (err: unknown) {
        const message = err instanceof Error ? err.message : "Unknown error";
        return NextResponse.json(
            { error: "TTS service is currently unavailable.", details: message },
            { status: 503 }
        );
    }
}
