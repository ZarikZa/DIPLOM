package com.example.hhdiplom.api;

import android.util.Log;

import java.io.IOException;

import okhttp3.MediaType;
import okhttp3.RequestBody;
import okio.Buffer;
import okio.BufferedSink;
import okio.ForwardingSink;
import okio.Okio;
import okio.Sink;

public class ProgressRequestBody extends RequestBody {

    public interface Listener {
        void onProgress(long bytesWritten, long contentLength);
    }

    private static final String TAG = "UPLOAD_PROGRESS";

    private final RequestBody delegate;
    private final Listener listener;

    public ProgressRequestBody(RequestBody delegate, Listener listener) {
        this.delegate = delegate;
        this.listener = listener;
    }

    @Override
    public MediaType contentType() {
        return delegate.contentType();
    }

    @Override
    public long contentLength() throws IOException {
        return delegate.contentLength();
    }

    @Override
    public void writeTo(BufferedSink sink) throws IOException {
        long contentLength = contentLength();
        Sink forwarding = new ForwardingSink(sink) {
            long written = 0L;
            long lastLogAt = 0L;

            @Override
            public void write(Buffer source, long byteCount) throws IOException {
                super.write(source, byteCount);
                written += byteCount;

                if (listener != null) listener.onProgress(written, contentLength);

                // чтобы не спамить лог каждую миллисекунду — лог раз в ~256KB
                if (written - lastLogAt >= 256 * 1024) {
                    lastLogAt = written;
                    Log.d(TAG, "sent " + written + " / " + contentLength);
                }
            }
        };

        BufferedSink bufferedSink = Okio.buffer(forwarding);
        delegate.writeTo(bufferedSink);
        bufferedSink.flush();

        Log.d(TAG, "DONE sent " + contentLength + " bytes");
    }
}
