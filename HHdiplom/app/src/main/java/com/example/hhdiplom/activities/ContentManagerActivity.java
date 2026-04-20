package com.example.hhdiplom.activities;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.recyclerview.widget.LinearLayoutManager;
import androidx.recyclerview.widget.RecyclerView;

import com.example.hhdiplom.R;
import com.example.hhdiplom.adapters.CmVacancyAdapter;
import com.example.hhdiplom.api.ApiClient;
import com.example.hhdiplom.models.Vacancy;
import com.example.hhdiplom.models.VacancyResponse;

import java.util.ArrayList;

import retrofit2.Call;
import retrofit2.Callback;
import retrofit2.Response;

public class ContentManagerActivity extends AppCompatActivity implements CmVacancyAdapter.OnVacancyActionListener {

    private RecyclerView recycler;
    private ProgressBar progress;
    private TextView tvEmpty;
    private CmVacancyAdapter adapter;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_content_manager);

        findViewById(R.id.btnBackCM).setOnClickListener(v -> finish());

        recycler = findViewById(R.id.recyclerCMVacancies);
        progress = findViewById(R.id.progressCM);
        tvEmpty = findViewById(R.id.tvCMEmpty);

        recycler.setLayoutManager(new LinearLayoutManager(this));
        adapter = new CmVacancyAdapter(new ArrayList<>(), this);
        recycler.setAdapter(adapter);

        loadVacancies();
    }

    private void loadVacancies() {
        progress.setVisibility(View.VISIBLE);
        tvEmpty.setVisibility(View.GONE);

        ApiClient.getApiService().getVacancies(null,null,null,null,null,null,null,null,null,1).enqueue(new Callback<VacancyResponse>() {
            @Override
            public void onResponse(@NonNull Call<VacancyResponse> call, @NonNull Response<VacancyResponse> response) {
                progress.setVisibility(View.GONE);
                if (response.isSuccessful() && response.body() != null && response.body().getResults() != null) {
                    adapter.setItems(response.body().getResults());
                    tvEmpty.setVisibility(response.body().getResults().isEmpty() ? View.VISIBLE : View.GONE);
                } else {
                    tvEmpty.setVisibility(View.VISIBLE);
                }
            }

            @Override
            public void onFailure(@NonNull Call<VacancyResponse> call, @NonNull Throwable t) {
                progress.setVisibility(View.GONE);
                tvEmpty.setVisibility(View.VISIBLE);
                Toast.makeText(ContentManagerActivity.this, "Сетевая ошибка", Toast.LENGTH_SHORT).show();
            }
        });
    }

    @Override
    public void onUploadVideoClicked(Vacancy vacancy) {
        Intent i = new Intent(this, UploadVideoActivity.class);
        i.putExtra("vacancy_id", vacancy.getId());
        i.putExtra("vacancy_title", vacancy.getPosition());
        startActivity(i);
    }
}
