import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '@/views/HomeView.vue'
import SettingsView from '@/views/SettingsView.vue'
import TaskListView from '@/views/TaskListView.vue'
import WorkspaceView from '@/views/WorkspaceView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/workspace/:assetId', component: WorkspaceView },
    { path: '/tasks', component: TaskListView },
    { path: '/settings', component: SettingsView },
  ],
})
