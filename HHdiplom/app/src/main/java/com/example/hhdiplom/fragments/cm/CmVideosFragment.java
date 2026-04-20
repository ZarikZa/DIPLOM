package com.example.hhdiplom.fragments.cm;

import android.os.Bundle;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.GridLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.adapters.CmVideosGridAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.UploadGate;
import com.example.hhdiplom.models.CmVideoItem;
import com.example.hhdiplom.models.CmVideoResponse;

import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/**
 * CM: TikTok-style grid 3xN
 */
public class CmVideosFragment extends Fragment {

    private RecyclerView recycler;
    private ProgressBar progress;
    private TextView empty;

    private CmVideosGridAdapter adapter;
    private final List<CmVideoItem> items = new ArrayList<>();

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View v = inflater.inflate(R.layout.fragment_cm_videos, container, false);

        recycler = v.findViewById(R.id.recycler);
        progress = v.findViewById(R.id.progress);
        empty = v.findViewById(R.id.empty);

        recycler.setLayoutManager(new GridLayoutManager(requireContext(), 3));
        adapter = new CmVideosGridAdapter(items);
        recycler.setAdapter(adapter);

        load(1);
        return v;
    }

    private void load(int page) {
        progress.setVisibility(View.VISIBLE);
        empty.setVisibility(View.GONE);
        if (UploadGate.isUploading()) {
            Log.w("CM", "Skip loading videos: upload in progress");
            return;
        }

        ApiClient.getApiService().getContentManagerVideos(page).enqueue(new Callback<CmVideoResponse>() {
            @Override
            public void onResponse(@NonNull Call<CmVideoResponse> call, @NonNull Response<CmVideoResponse> response) {
                progress.setVisibility(View.GONE);
                if (!isAdded()) return;

                if (response.isSuccessful() && response.body() != null) {
                    items.clear();
                    if (response.body().getResults() != null) {
                        items.addAll(response.body().getResults());
                    }
                    adapter.notifyDataSetChanged();

                    if (items.isEmpty()) {
                        empty.setText("Пока нет видео");
                        empty.setVisibility(View.VISIBLE);
                    }
                } else {
                    empty.setText("Не удалось загрузить видео (" + response.code() + ")");
                    empty.setVisibility(View.VISIBLE);
                }
            }

            @Override
            public void onFailure(@NonNull Call<CmVideoResponse> call, @NonNull Throwable t) {
                progress.setVisibility(View.GONE);
                if (!isAdded()) return;
                empty.setText("Ошибка сети: " + t.getMessage());
                empty.setVisibility(View.VISIBLE);
            }
        });
    }
}
