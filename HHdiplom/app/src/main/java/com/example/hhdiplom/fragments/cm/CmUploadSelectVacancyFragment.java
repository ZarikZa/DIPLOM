package com.example.hhdiplom.fragments.cm;

import android.content.Intent;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.Log;
import android.view.*;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.fragment.app.Fragment;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.activities.UploadVideoActivity;
import com.example.hhdiplom.adapters.CmUploadVacancyAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.UploadGate;
import com.example.hhdiplom.models.CmVideoItem;
import com.example.hhdiplom.models.CmVideoResponse;
import com.example.hhdiplom.models.Vacancy;
import com.example.hhdiplom.models.VacancyResponse;

import java.util.*;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

/**
 * CM: экран выбора вакансии перед загрузкой видео.
 * Логика: берём вакансии CM + берём видео CM → фильтруем вакансии, где сейчас меньше 3 видео.
 */
public class CmUploadSelectVacancyFragment extends Fragment implements CmUploadVacancyAdapter.OnVacancyPickListener {
    private static final int MAX_VIDEOS_PER_VACANCY = 3;

    private RecyclerView recycler;
    private ProgressBar progress;
    private TextView empty;
    private EditText searchEditText;

    private CmUploadVacancyAdapter adapter;
    private final List<Vacancy> items = new ArrayList<>();

    // Счётчик видео на каждой вакансии.
    private final Map<Integer, Integer> vacancyVideoCounts = new HashMap<>();

    // временные буферы
    private final List<Vacancy> allVacancies = new ArrayList<>();
    private final List<Vacancy> eligibleVacancies = new ArrayList<>();

    private final ActivityResultLauncher<Intent> uploadVideoLauncher =
            registerForActivityResult(new ActivityResultContracts.StartActivityForResult(), result -> {
                if (!isAdded()) return;
                if (result.getResultCode() == android.app.Activity.RESULT_OK) {
                    load();
                }
            });

    @Nullable
    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, @Nullable ViewGroup container, @Nullable Bundle savedInstanceState) {
        View v = inflater.inflate(R.layout.fragment_cm_upload_select, container, false);

        recycler = v.findViewById(R.id.recycler);
        progress = v.findViewById(R.id.progress);
        empty = v.findViewById(R.id.empty);
        searchEditText = v.findViewById(R.id.searchEditText);

        recycler.setLayoutManager(new LinearLayoutManager(getContext()));
        adapter = new CmUploadVacancyAdapter(items, this);
        recycler.setAdapter(adapter);
        setupSearch();

        load();
        return v;
    }

    private void setupSearch() {
        if (searchEditText == null) return;

        searchEditText.addTextChangedListener(new TextWatcher() {
            @Override
            public void beforeTextChanged(CharSequence s, int start, int count, int after) {
            }

            @Override
            public void onTextChanged(CharSequence s, int start, int before, int count) {
            }

            @Override
            public void afterTextChanged(Editable s) {
                applyFilters();
            }
        });
    }

    private void load() {
        progress.setVisibility(View.VISIBLE);
        empty.setVisibility(View.GONE);

        items.clear();
        adapter.notifyDataSetChanged();

        vacancyVideoCounts.clear();
        allVacancies.clear();
        eligibleVacancies.clear();

        // 1) грузим все CM видео (все страницы)
        loadCmVideosPage(1);
    }

    private void loadCmVideosPage(int page) {
        if (UploadGate.isUploading()) {
            Log.w("CM", "Skip loading videos: upload in progress");
            return;
        }

        ApiClient.getApiService().getContentManagerVideos(page).enqueue(new Callback<CmVideoResponse>() {
            @Override
            public void onResponse(@NonNull Call<CmVideoResponse> call, @NonNull Response<CmVideoResponse> response) {
                if (!isAdded()) return;

                if (!response.isSuccessful() || response.body() == null) {
                    // даже если видео не получили — всё равно попробуем загрузить вакансии
                    loadCmVacanciesPage(1);
                    return;
                }

                List<CmVideoItem> res = response.body().getResults();
                if (res != null) {
                    for (CmVideoItem it : res) {
                        int vacancyId = it.getVacancyId();
                        int count = vacancyVideoCounts.containsKey(vacancyId)
                                ? vacancyVideoCounts.get(vacancyId)
                                : 0;
                        vacancyVideoCounts.put(vacancyId, count + 1);
                    }
                }

                if (response.body().getNext() != null) {
                    loadCmVideosPage(page + 1);
                } else {
                    // 2) после видео — грузим вакансии
                    loadCmVacanciesPage(1);
                }
            }

            @Override
            public void onFailure(@NonNull Call<CmVideoResponse> call, @NonNull Throwable t) {
                if (!isAdded()) return;
                // не падаем — просто считаем, что видео нет
                loadCmVacanciesPage(1);
            }
        });
    }

    private void loadCmVacanciesPage(int page) {
        ApiClient.getApiService().getContentManagerVacancies(page).enqueue(new Callback<VacancyResponse>() {
            @Override
            public void onResponse(@NonNull Call<VacancyResponse> call, @NonNull Response<VacancyResponse> response) {
                if (!isAdded()) return;

                if (!response.isSuccessful() || response.body() == null || response.body().getResults() == null) {
                    progress.setVisibility(View.GONE);
                    empty.setText("Не удалось загрузить вакансии (" + response.code() + ")");
                    empty.setVisibility(View.VISIBLE);
                    return;
                }

                allVacancies.addAll(response.body().getResults());

                if (response.body().getNext() != null) {
                    loadCmVacanciesPage(page + 1);
                    return;
                }

                // 3) фильтрация: показываем вакансии, где можно добавить ещё видео (менее 3)
                eligibleVacancies.clear();
                for (Vacancy v : allVacancies) {
                    int videosCount = vacancyVideoCounts.containsKey(v.getId())
                            ? vacancyVideoCounts.get(v.getId())
                            : 0;
                    if (videosCount < MAX_VIDEOS_PER_VACANCY) {
                        eligibleVacancies.add(v);
                    }
                }

                progress.setVisibility(View.GONE);
                applyFilters();
            }

            @Override
            public void onFailure(@NonNull Call<VacancyResponse> call, @NonNull Throwable t) {
                if (!isAdded()) return;
                progress.setVisibility(View.GONE);
                empty.setText("Ошибка сети: " + t.getMessage());
                empty.setVisibility(View.VISIBLE);
            }
        });
    }

    private void applyFilters() {
        String query = searchEditText != null ? searchEditText.getText().toString().trim().toLowerCase(Locale.ROOT) : "";

        items.clear();
        if (query.isEmpty()) {
            items.addAll(eligibleVacancies);
        } else {
            for (Vacancy vacancy : eligibleVacancies) {
                String position = vacancy.getPosition() == null ? "" : vacancy.getPosition().toLowerCase(Locale.ROOT);
                String city = vacancy.getCity() == null ? "" : vacancy.getCity().toLowerCase(Locale.ROOT);
                String company = vacancy.getCompanyName() == null ? "" : vacancy.getCompanyName().toLowerCase(Locale.ROOT);
                if (position.contains(query) || city.contains(query) || company.contains(query)) {
                    items.add(vacancy);
                }
            }
        }

        adapter.notifyDataSetChanged();

        if (eligibleVacancies.isEmpty()) {
            empty.setText("Все вакансии уже достигли лимита в 3 видео ✅\n(или вакансий нет)");
            empty.setVisibility(View.VISIBLE);
            return;
        }

        if (items.isEmpty()) {
            empty.setText("По вашему запросу ничего не найдено");
            empty.setVisibility(View.VISIBLE);
            return;
        }

        empty.setVisibility(View.GONE);
    }

    @Override
    public void onPickVacancy(Vacancy vacancy) {
        if (getContext() == null) return;

        Intent i = new Intent(requireContext(), UploadVideoActivity.class);
        i.putExtra("vacancy_id", vacancy.getId());
        i.putExtra("vacancy_title", vacancy.getPosition());
        i.putExtra("vacancy_city", vacancy.getCity());
        uploadVideoLauncher.launch(i);
    }
}
