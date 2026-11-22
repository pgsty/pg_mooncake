use moonlink_service::{start_with_config, ServiceConfig};
use pgrx::bgworkers::{
    BackgroundWorker, BackgroundWorkerBuilder, BackgroundWorkerStatus, BgWorkerStartTime,
    DynamicBackgroundWorker, SignalWakeFlags,
};
use pgrx::prelude::*;
use std::time::Duration;

pub(crate) fn init() {
    BackgroundWorkerBuilder::new("moonlink")
        .set_library("pg_mooncake")
        .set_function("moonlink_main")
        .enable_shmem_access(None)
        // Not on a standby: moonlink can't replicate from a read-only server, and its attempts would error the
        // mirrors. Postgres starts the worker once recovery ends, at startup or on promotion.
        .set_start_time(BgWorkerStartTime::RecoveryFinished)
        .set_restart_time(Some(Duration::from_secs(15)))
        .load();
}

#[pg_guard]
#[no_mangle]
extern "C-unwind" fn moonlink_main(_arg: pg_sys::Datum) {
    std::env::set_var("RUST_BACKTRACE", "1");
    BackgroundWorker::attach_signal_handlers(SignalWakeFlags::SIGTERM);
    // moonlink's own SIGTERM handling (tokio::signal) chains to the pgrx handler above, which calls into Postgres and
    // panics on any thread but this one; the panic can also lose the shutdown request. A signal sent to the process
    // goes to a thread that doesn't block it, so every moonlink thread blocks the shutdown signals and only this
    // thread, which just waits for moonlink, receives them. Threads inherit the mask of the thread that creates them:
    // the moonlink thread and the runtime's workers are created while this thread blocks the signals, and
    // on_thread_start also covers blocking-pool threads started later. SIGQUIT (immediate shutdown) stays deliverable
    // everywhere.
    //
    // moonlink runs under block_on on its own thread, not as a task on the runtime: as a task, its shutdown races make
    // fast stops crash the worker far more often.
    let original_mask = block_shutdown_signals();
    let runtime = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .on_thread_start(|| {
            block_shutdown_signals();
        })
        .build()
        .expect("failed to build the moonlink runtime");
    // The main thread's stack size: moonlink's startup and recovery run inline in this future, and have overflowed a
    // smaller stack in debug builds.
    let moonlink = std::thread::Builder::new()
        .name("moonlink".to_owned())
        .stack_size(MOONLINK_THREAD_STACK_SIZE)
        .spawn(move || runtime.block_on(start_with_config(service_config())))
        .expect("failed to start the moonlink thread");
    set_signal_mask(&original_mask);
    wait_for_moonlink(&moonlink);
    // An error is raised here, under pg_guard, so it is reported like any other worker error.
    match moonlink.join() {
        Ok(result) => result.unwrap(),
        Err(panic) => std::panic::resume_unwind(panic),
    }
    // moonlink returns only after SIGTERM. Postgres restarts a background worker only after a non-zero exit, so a
    // SIGTERM outside a server shutdown (a kill from outside Postgres: the worker isn't in the ProcArray, so
    // pg_terminate_backend can't reach it) would otherwise leave every mirror without moonlink until the next server
    // restart. A shutdown stays a clean exit.
    if !postmaster_stopping() {
        log!("moonlink stopped on SIGTERM outside a server shutdown; exiting with code 1 so that it is restarted");
        unsafe { pg_sys::proc_exit(1) };
    }
}

const MOONLINK_THREAD_STACK_SIZE: usize = 8 << 20;

/// Waits for the moonlink thread to finish. A SIGTERM that arrives before moonlink has installed its own handler
/// reaches only pgrx's, and moonlink would never stop: once one has arrived, raise it again on this thread (the only
/// one that takes it) until moonlink is gone. moonlink waits for SIGTERM once, so repeats are harmless.
fn wait_for_moonlink(moonlink: &std::thread::JoinHandle<moonlink_service::Result<()>>) {
    const POLL_INTERVAL: Duration = Duration::from_millis(200);
    const RAISE_INTERVAL: Duration = Duration::from_secs(2);
    let mut last_raise: Option<std::time::Instant> = None;
    let mut sigterm = false;
    let mut next_status_check = std::time::Instant::now() + RAISE_INTERVAL;
    let mut next_sweep = std::time::Instant::now() + Duration::from_secs(5);
    let mut pending = std::collections::VecDeque::new();
    let mut worker: Option<DynamicBackgroundWorker> = None;
    let mut handles = pgrx::PgMemoryContexts::new("moonlink cleanup worker handle");
    while !moonlink.is_finished() {
        unsafe {
            pg_sys::WaitLatch(
                pg_sys::MyLatch,
                (pg_sys::WL_LATCH_SET | pg_sys::WL_TIMEOUT | pg_sys::WL_EXIT_ON_PM_DEATH) as _,
                POLL_INTERVAL.as_millis() as _,
                pg_sys::PG_WAIT_EXTENSION,
            );
            pg_sys::ResetLatch(pg_sys::MyLatch);
        }
        sigterm |= BackgroundWorker::sigterm_received();
        if !sigterm && std::time::Instant::now() >= next_status_check {
            sigterm = postmaster_stopping();
            next_status_check = std::time::Instant::now() + RAISE_INTERVAL;
        }
        if !sigterm {
            if pending.is_empty() && std::time::Instant::now() >= next_sweep {
                if let Ok(names) = crate::utils::rpc!(timeout = Duration::from_secs(1); moonlink_rpc::registered_databases)
                {
                    pending.extend(names.into_iter().filter(|name| {
                        name.len() < pg_sys::NAMEDATALEN as usize && !name.contains('\0')
                    }));
                }
                next_sweep = std::time::Instant::now() + Duration::from_secs(30);
            }
            if worker
                .as_ref()
                .is_none_or(|child| matches!(child.pid(), Err(BackgroundWorkerStatus::Stopped)))
            {
                if let Some(name) = pending.pop_front() {
                    worker = unsafe {
                        handles.reset();
                        handles.switch_to(|_| {
                            BackgroundWorkerBuilder::new("moonlink mirror cleanup")
                                .set_library("pg_mooncake")
                                .set_function("mooncake_cleanup_main")
                                .enable_spi_access()
                                .set_extra(&name)
                                .load_dynamic()
                                .ok()
                        })
                    };
                }
            }
        }
        if sigterm
            && !moonlink.is_finished()
            && last_raise.is_none_or(|at| at.elapsed() >= RAISE_INTERVAL)
        {
            unsafe { libc::raise(libc::SIGTERM) };
            last_raise = Some(std::time::Instant::now());
        }
    }
}

#[pg_guard]
#[no_mangle]
extern "C-unwind" fn mooncake_cleanup_main(_arg: pg_sys::Datum) {
    BackgroundWorker::connect_worker_to_spi(Some(BackgroundWorker::get_extra()), None);
    BackgroundWorker::transaction(|| {
        Spi::run("SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL READ COMMITTED")
            .expect("setting cleanup isolation");
    });
    BackgroundWorker::transaction(|| {
        let extension = unsafe { pg_sys::get_extension_oid(c"pg_mooncake".as_ptr(), true) };
        if extension == pg_sys::InvalidOid {
            return;
        }
        unsafe {
            pg_sys::LockDatabaseObject(
                pg_sys::ExtensionRelationId,
                extension,
                0,
                pg_sys::AccessShareLock as _,
            )
        };
        let installed = Spi::get_one::<bool>("SELECT EXISTS (SELECT FROM pg_catalog.pg_depend d JOIN pg_catalog.pg_extension e ON e.oid=d.refobjid WHERE d.classid='pg_catalog.pg_proc'::pg_catalog.regclass AND d.objid=pg_catalog.to_regprocedure('mooncake._reconcile_creates()') AND d.refclassid='pg_catalog.pg_extension'::pg_catalog.regclass AND d.deptype='e' AND e.extname='pg_mooncake')").expect("checking mirror cleanup membership");
        if installed == Some(true) {
            crate::drop_tracking::reconcile();
            Spi::run("SELECT mooncake._reconcile_creates()")
                .expect("reconciling interrupted mirror creation");
        }
    });
}

/// Whether the postmaster is shutting down. It records "stopping" in postmaster.pid (the PM_STATUS line) for smart,
/// fast and immediate shutdowns before it signals any child, so a worker that got SIGTERM because of a shutdown
/// always sees it. Unreadable counts as not stopping: an extra restart is better than a worker that stays down.
fn postmaster_stopping() -> bool {
    const LOCK_FILE_LINE_PM_STATUS: usize = 8;
    std::fs::read("postmaster.pid")
        .ok()
        .and_then(|pid_file| {
            pid_file
                .split(|byte| *byte == b'\n')
                .nth(LOCK_FILE_LINE_PM_STATUS - 1)
                .map(|status| status.trim_ascii() == b"stopping")
        })
        .unwrap_or(false)
}

/// Blocks SIGTERM, SIGHUP and SIGINT on the calling thread and returns its previous signal mask.
fn block_shutdown_signals() -> libc::sigset_t {
    unsafe {
        let mut signals: libc::sigset_t = std::mem::zeroed();
        libc::sigemptyset(&mut signals);
        for signal in [libc::SIGTERM, libc::SIGHUP, libc::SIGINT] {
            libc::sigaddset(&mut signals, signal);
        }
        let mut previous: libc::sigset_t = std::mem::zeroed();
        let rc = libc::pthread_sigmask(libc::SIG_BLOCK, &signals, &mut previous);
        assert_eq!(rc, 0, "pthread_sigmask failed");
        previous
    }
}

fn set_signal_mask(mask: &libc::sigset_t) {
    let rc = unsafe { libc::pthread_sigmask(libc::SIG_SETMASK, mask, std::ptr::null_mut()) };
    assert_eq!(rc, 0, "pthread_sigmask failed");
}

fn service_config() -> ServiceConfig {
    ServiceConfig {
        base_path: crate::data_directory::data_directory(),
    }
}
