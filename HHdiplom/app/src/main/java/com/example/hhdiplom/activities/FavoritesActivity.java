package com.example.hhdiplom.activities;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ImageButton;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.Nullable;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.VacancyAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.api.ApiService;
import com.example.hhdiplom.models.Vacancy;
import com.example.hhdiplom.models.VacancyResponse;

import java.util.ArrayList;
import java.util.List;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class FavoritesActivity extends AppCompatActivity {

    private ApiService apiService;
    private ProgressBar progressBar;
    private RecyclerView recyclerView;
    private TextView tvEmpty;

    private VacancyAdapter adapter;
    private final List<Vacancy> items = new ArrayList<>();

    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_favorites);

        ApiClient.init(this);
        apiService = ApiClient.getApiService();

        progressBar = findViewById(R.id.progressBar);
        recyclerView = findViewById(R.id.recyclerView);
        tvEmpty = findViewById(R.id.tvEmpty);
        ImageButton btnBack = findViewById(R.id.btnBack);

        btnBack.setOnClickListener(v -> finish());

        adapter = new VacancyAdapter(items, new VacancyAdapter.OnVacancyClickListener() {
            @Override
            public void onVacancyClick(Vacancy vacancy) {
                Intent i = new Intent(FavoritesActivity.this, VacancyDetailsActivity.class);
                i.putExtra("vacancy_id", vacancy.getId());
                startActivity(i);
            }

            @Override
            public void onApplyClick(Vacancy vacancy) {
                Intent i = new Intent(FavoritesActivity.this, VacancyDetailsActivity.class);
                i.putExtra("vacancy_id", vacancy.getId());
                startActivity(i);
            }

            @Override
            public void onVideoClick(Vacancy vacancy) {
            }
        });

        recyclerView.setLayoutManager(new LinearLayoutManager(this));
        recyclerView.setAdapter(adapter);

        loadFavorites(1);
    }

    private void loadFavorites(int page) {
        progressBar.setVisibility(View.VISIBLE);
        tvEmpty.setVisibility(View.GONE);

        Call<VacancyResponse> call = apiService.getVacancies(
                null, null, null, null, null,
                null, null,
                true,
                null,
                page
        );

        call.enqueue(new Callback<VacancyResponse>() {
            @Override
            public void onResponse(Call<VacancyResponse> call, Response<VacancyResponse> response) {
                progressBar.setVisibility(View.GONE);

                if (response.isSuccessful() && response.body() != null) {
                    List<Vacancy> vacs = response.body().getResults();
                    items.clear();
                    if (vacs != null) {
                        items.addAll(vacs);
                    }
                    adapter.updateList(items);

                    if (items.isEmpty()) {
                        tvEmpty.setVisibility(View.VISIBLE);
                    }
                } else {
                    Toast.makeText(FavoritesActivity.this, getString(R.string.favorite_error_code, response.code()), Toast.LENGTH_SHORT).show();
                }
            }

            @Override
            public void onFailure(Call<VacancyResponse> call, Throwable t) {
                progressBar.setVisibility(View.GONE);
                Toast.makeText(FavoritesActivity.this, getString(R.string.error_network_with_message, t.getMessage()), Toast.LENGTH_SHORT).show();
            }
        });
    }
}
