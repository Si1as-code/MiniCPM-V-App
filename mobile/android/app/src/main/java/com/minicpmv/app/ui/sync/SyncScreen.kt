package com.minicpmv.app.ui.sync

import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.minicpmv.app.viewmodel.MainViewModel

/**
 * 数据同步管理页面
 */
@Composable
fun SyncScreen(
    modifier: Modifier = Modifier,
    viewModel: MainViewModel = viewModel()
) {
    val syncState by viewModel.syncState

    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        when (val state = syncState) {
            is MainViewModel.SyncState.Idle -> {
                SyncIdleView(onSync = { viewModel.triggerSync() })
            }
            is MainViewModel.SyncState.Syncing -> {
                SyncInProgressView()
            }
            is MainViewModel.SyncState.Success -> {
                SyncSuccessView(message = state.message, onSync = { viewModel.triggerSync() })
            }
            is MainViewModel.SyncState.Error -> {
                SyncErrorView(message = state.message, onRetry = { viewModel.triggerSync() })
            }
        }
    }
}

@Composable
private fun SyncIdleView(onSync: () -> Unit) {
    Icon(
        Icons.Filled.Sync,
        contentDescription = null,
        modifier = Modifier.size(80.dp),
        tint = MaterialTheme.colorScheme.primary
    )
    Spacer(modifier = Modifier.height(16.dp))
    Text("数据同步", style = MaterialTheme.typography.headlineMedium)
    Spacer(modifier = Modifier.height(8.dp))
    Text("将本地识别记录同步到云端", style = MaterialTheme.typography.bodyMedium)
    Spacer(modifier = Modifier.height(32.dp))
    Button(onClick = onSync) {
        Text("开始同步")
    }
}

@Composable
private fun SyncInProgressView() {
    CircularProgressIndicator(modifier = Modifier.size(64.dp))
    Spacer(modifier = Modifier.height(16.dp))
    Text("同步中...", style = MaterialTheme.typography.headlineSmall)
}

@Composable
private fun SyncSuccessView(message: String, onSync: () -> Unit) {
    Icon(
        Icons.Filled.CheckCircle,
        contentDescription = null,
        modifier = Modifier.size(80.dp),
        tint = MaterialTheme.colorScheme.primary
    )
    Spacer(modifier = Modifier.height(16.dp))
    Text("同步成功", style = MaterialTheme.typography.headlineMedium)
    Spacer(modifier = Modifier.height(8.dp))
    Text(message, style = MaterialTheme.typography.bodyMedium)
    Spacer(modifier = Modifier.height(32.dp))
    Button(onClick = onSync) {
        Text("再次同步")
    }
}

@Composable
private fun SyncErrorView(message: String, onRetry: () -> Unit) {
    Icon(
        Icons.Filled.Error,
        contentDescription = null,
        modifier = Modifier.size(80.dp),
        tint = MaterialTheme.colorScheme.error
    )
    Spacer(modifier = Modifier.height(16.dp))
    Text("同步失败", style = MaterialTheme.typography.headlineMedium)
    Spacer(modifier = Modifier.height(8.dp))
    Text(message, style = MaterialTheme.typography.bodyMedium)
    Spacer(modifier = Modifier.height(32.dp))
    Button(onClick = onRetry) {
        Text("重试")
    }
}
