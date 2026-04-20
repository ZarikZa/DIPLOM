package com.example.hhdiplom.fragments;

import android.content.Intent;
import android.os.Bundle;
import android.util.Log;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import androidx.viewpager2.widget.ViewPager2;

import com.example.hhdiplom.R;
import com.example.hhdiplom.activities.VacancyDetailsActivity;
import com.example.hhdiplom.adapters.VideoAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.FeedVideoItem;
import com.example.hhdiplom.models.FeedVideoResponse;
import com.google.android.exoplayer2.ExoPlayer;
import com.google.android.exoplayer2.Player;

import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class FeedVideoFragment extends Fragment {

    private static final String TAG = "FeedVideoFragment";

    private ViewPager2 viewPager2;
    private ExoPlayer player;

    private final List<FeedVideoItem> videos = new ArrayList<>();
    private VideoAdapter videoAdapter;

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater,
                             @Nullable ViewGroup container,
                             @Nullable Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_feed_video, container, false);
    }

    @Override
    public void onViewCreated(@NonNull View view, @Nullable Bundle savedInstanceState) {
        super.onViewCreated(view, savedInstanceState);

        viewPager2 = view.findViewById(R.id.viewPagerVideos);

        player = new ExoPlayer.Builder(requireContext()).build();
        player.setRepeatMode(Player.REPEAT_MODE_ALL);

        videoAdapter = new VideoAdapter(requireContext(), videos, player, new VideoAdapter.OnVideoInteractionListener() {
            @Override
            public void onLikeClicked(FeedVideoItem video, int position) {
            }

            @Override
            public void onVideoViewed(FeedVideoItem video) {
                ApiClient.getApiService().viewVideo(video.getId()).enqueue(new Callback<Void>() {
                    @Override public void onResponse(@NonNull Call<Void> call, @NonNull Response<Void> response) {}
                    @Override public void onFailure(@NonNull Call<Void> call, @NonNull Throwable t) {}
                });
            }

            @Override
            public void onVacancyClicked(FeedVideoItem video) {
                if (player != null) player.pause();

                Intent intent = new Intent(requireContext(), VacancyDetailsActivity.class);
                Integer vacancyId = extractVacancyId(video);
                if (vacancyId == null || vacancyId <= 0) {
                    Toast.makeText(requireContext(), getString(R.string.video_vacancy_unavailable), Toast.LENGTH_SHORT).show();
                    return;
                }
                intent.putExtra("vacancy_id", vacancyId);
                startActivity(intent);
            }

        });

        viewPager2.setAdapter(videoAdapter);
        viewPager2.setOrientation(ViewPager2.ORIENTATION_VERTICAL);
        viewPager2.setOffscreenPageLimit(1);
        viewPager2.setUserInputEnabled(true);

        viewPager2.registerOnPageChangeCallback(new ViewPager2.OnPageChangeCallback() {
            @Override
            public void onPageSelected(int position) {
                super.onPageSelected(position);

                viewPager2.post(() -> {
                    if (videoAdapter != null) videoAdapter.playVideoAtPosition(position);
                });
            }
        });

        fetchVideos();
    }

    private void fetchVideos() {
        ApiService apiService = ApiClient.getApiService();
        String userType = ApiClient.getUserType();
        boolean isApplicant = userType != null && "applicant".equalsIgnoreCase(userType.trim());

        if (!isApplicant) {
            fetchFallback(apiService);
            return;
        }

        apiService.getRecommendedVideoFeed().enqueue(new Callback<FeedVideoResponse>() {
            @Override
            public void onResponse(@NonNull Call<FeedVideoResponse> call,
                                   @NonNull Response<FeedVideoResponse> response) {
                if (!isAdded()) return;

                if (!response.isSuccessful()) {
                    Log.w(TAG, "Recommended feed not available: " + response.code());
                    fetchFallback(apiService);
                    return;
                }

                FeedVideoResponse body = response.body();
                if (body == null || body.getResults() == null) {
                    Log.w(TAG, "Recommended feed empty body/results");
                    fetchFallback(apiService);
                    return;
                }

                applyNewList(body.getResults());
            }

            @Override
            public void onFailure(@NonNull Call<FeedVideoResponse> call, @NonNull Throwable t) {
                if (!isAdded()) return;
                Log.e(TAG, "Recommended feed error", t);
                fetchFallback(apiService);
            }
        });
    }

    private void fetchFallback(ApiService apiService) {
        apiService.getVideoFeed().enqueue(new Callback<FeedVideoResponse>() {
            @Override
            public void onResponse(@NonNull Call<FeedVideoResponse> call,
                                   @NonNull Response<FeedVideoResponse> response) {
                if (!isAdded()) return;

                if (!response.isSuccessful() || response.body() == null || response.body().getResults() == null) {
                    Log.e(TAG, "Video feed error: " + response.code());
                    Toast.makeText(requireContext(), getString(R.string.video_feed_load_error_code, response.code()), Toast.LENGTH_SHORT).show();
                    return;
                }

                applyNewList(response.body().getResults());
            }

            @Override
            public void onFailure(@NonNull Call<FeedVideoResponse> call, @NonNull Throwable t) {
                if (!isAdded()) return;
                Log.e(TAG, "Video feed failure", t);
                Toast.makeText(requireContext(), getString(R.string.video_feed_load_network_error), Toast.LENGTH_SHORT).show();
            }
        });
    }

    private void applyNewList(@NonNull List<FeedVideoItem> newItems) {
        videos.clear();
        videos.addAll(newItems);
        videoAdapter.notifyDataSetChanged();

        if (!videos.isEmpty()) {
            viewPager2.setCurrentItem(0, false);
            viewPager2.post(() -> videoAdapter.playVideoAtPosition(0));
            viewPager2.postDelayed(() -> {
                if (!isAdded() || videoAdapter == null || videos.isEmpty()) {
                    return;
                }
                if (viewPager2.getCurrentItem() == 0) {
                    videoAdapter.playVideoAtPosition(0);
                }
            }, 300);
        } else {
            Toast.makeText(requireContext(), getString(R.string.video_feed_empty), Toast.LENGTH_SHORT).show();
        }
    }

    /**
     * Твой бэк может отдавать vacancy либо:
     *  - объект {id: ...}
     *  - просто число
     * Поддержим оба варианта безопасно.
     */
    private Integer extractVacancyId(@NonNull FeedVideoItem item) {
        try {
            if (item.getVacancy() != null) {
                int id = item.getVacancy().getId();
                return id > 0 ? id : null;
            }
        } catch (Exception ignored) {}


        return null;
    }

    @Override
    public void onDestroyView() {
        super.onDestroyView();
        if (player != null) {
            player.release();
            player = null;
        }
    }

    @Override
    public void onResume() {
        super.onResume();
        if (videoAdapter != null && viewPager2 != null) {
            int pos = viewPager2.getCurrentItem();
            viewPager2.post(() -> videoAdapter.playVideoAtPosition(pos));
        }
    }



    @Override
    public void onStop() {
        super.onStop();
        if (player != null) {
            player.pause();
        }
    }

}
